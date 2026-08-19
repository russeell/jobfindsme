"""Job tracking: what the user has seen, and how they acted on jobs.

JobImpressionService records shown/new/changed/reopened/closed history;
JobStateService records saved/applied/rejected state. One module owns the
user's job memory.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    JobChangeType,
    JobDetails,
    JobLiveness,
    JobMatch,
    JobPosting,
    JobState,
    JobStateKind,
    JobSummary,
    SearchChanges,
)
from jobfindsme.importing.repository import JobRepository
from jobfindsme.storage import Database

Clock = Callable[[], datetime]

_DESCRIPTION_LIMIT = 20_000


@dataclass(frozen=True)
class RadarSelection:
    matches: tuple[JobMatch, ...]
    changes: SearchChanges


class JobImpressionService:
    """Persist what one Search Plan has actually shown to the user."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def counts(self, *, workspace_id: str, plan_id: str) -> tuple[int, int]:
        """Return (distinct jobs ever shown, total show events) for a plan."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS distinct_jobs,
                       COALESCE(SUM(shown_count), 0) AS total_shows
                FROM search_job_impressions
                WHERE workspace_id = ? AND plan_id = ?
                """,
                (workspace_id, plan_id),
            ).fetchone()
        return int(row["distinct_jobs"]), int(row["total_shows"])

    def closed_count(self, *, workspace_id: str, plan_id: str) -> int:
        """Return jobs shown by this plan whose latest state is closed."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS closed_jobs
                FROM search_job_impressions
                WHERE workspace_id = ? AND plan_id = ?
                  AND last_liveness = 'closed'
                """,
                (workspace_id, plan_id),
            ).fetchone()
        return int(row["closed_jobs"])

    def select_and_record(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        candidates: list[JobMatch],
        all_jobs: list[JobPosting],
        limit: int,
        include_seen: bool,
        now: datetime | None = None,
    ) -> RadarSelection:
        observed_at = now or datetime.now(UTC)
        with self.database.connect() as connection:
            impression_rows = connection.execute(
                """
                SELECT * FROM search_job_impressions
                WHERE workspace_id = ? AND plan_id = ?
                """,
                (workspace_id, plan_id),
            ).fetchall()
            impressions = {row["job_id"]: row for row in impression_rows}
            state_rows = connection.execute(
                """
                SELECT job_id, state FROM job_states WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchall()
            states = {row["job_id"]: JobStateKind(row["state"]) for row in state_rows}

            closed_job_ids = self._closed_since_last_search(
                impressions=impressions,
                all_jobs=all_jobs,
            )
            classified = [
                self._annotate(
                    match,
                    impressions.get(match.job.job_id),
                    states,
                    observed_at,
                )
                for match in candidates
            ]
            repeated = sum(
                item.change_type is JobChangeType.UNCHANGED for item in classified
            )
            visible = [
                item
                for item in classified
                if item.state is not JobStateKind.REJECTED
                and (  # daily push: never re-suggest applied jobs
                    include_seen or item.state is not JobStateKind.APPLIED
                )
                and (include_seen or item.change_type is not JobChangeType.UNCHANGED)
            ][:limit]

            self._record_visible(
                connection=connection,
                workspace_id=workspace_id,
                plan_id=plan_id,
                matches=visible,
                observed_at=observed_at,
            )
            self._record_closed(
                connection=connection,
                workspace_id=workspace_id,
                plan_id=plan_id,
                job_ids=closed_job_ids,
            )

        return RadarSelection(
            matches=tuple(visible),
            changes=SearchChanges(
                new=sum(item.change_type is JobChangeType.NEW for item in visible),
                changed=sum(
                    item.change_type is JobChangeType.CHANGED for item in visible
                ),
                reopened=sum(
                    item.change_type is JobChangeType.REOPENED for item in visible
                ),
                closed=len(closed_job_ids),
                repeated_suppressed=0 if include_seen else repeated,
                closed_job_ids=tuple(sorted(closed_job_ids)),
            ),
        )

    @staticmethod
    def _annotate(match, impression, states, observed_at) -> JobMatch:
        state = states.get(match.job.job_id, JobStateKind.DISCOVERED)
        if impression is None:
            return match.model_copy(
                update={
                    "state": state,
                    "first_seen_at": observed_at,
                    "change_type": JobChangeType.NEW,
                }
            )
        previous_liveness = JobLiveness(impression["last_liveness"])
        current_liveness = match.job.source.liveness
        if previous_liveness in {
            JobLiveness.CLOSED,
            JobLiveness.STALE,
        } and current_liveness not in {JobLiveness.CLOSED, JobLiveness.STALE}:
            change_type = JobChangeType.REOPENED
        elif impression["last_content_hash"] != match.job.content_hash:
            change_type = JobChangeType.CHANGED
        else:
            change_type = JobChangeType.UNCHANGED
        return match.model_copy(
            update={
                "state": state,
                "first_seen_at": datetime.fromisoformat(impression["first_shown_at"]),
                "change_type": change_type,
            }
        )

    @staticmethod
    def _closed_since_last_search(*, impressions, all_jobs) -> set[str]:
        current = {job.job_id: job for job in all_jobs}
        closed = set()
        for job_id, impression in impressions.items():
            job = current.get(job_id)
            if job is None:
                continue
            previous = JobLiveness(impression["last_liveness"])
            if previous not in {
                JobLiveness.CLOSED,
                JobLiveness.STALE,
            } and job.source.liveness in {JobLiveness.CLOSED, JobLiveness.STALE}:
                closed.add(job_id)
        return closed

    @staticmethod
    def _record_visible(
        *, connection, workspace_id, plan_id, matches, observed_at
    ) -> None:
        for match in matches:
            connection.execute(
                """
                INSERT INTO search_job_impressions (
                    workspace_id, plan_id, job_id, first_shown_at,
                    last_shown_at, shown_count, last_content_hash, last_liveness
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(workspace_id, plan_id, job_id) DO UPDATE SET
                    last_shown_at = excluded.last_shown_at,
                    shown_count = search_job_impressions.shown_count + 1,
                    last_content_hash = excluded.last_content_hash,
                    last_liveness = excluded.last_liveness
                """,
                (
                    workspace_id,
                    plan_id,
                    match.job.job_id,
                    observed_at.isoformat(),
                    observed_at.isoformat(),
                    match.job.content_hash,
                    match.job.source.liveness,
                ),
            )

    @staticmethod
    def _record_closed(*, connection, workspace_id, plan_id, job_ids) -> None:
        connection.executemany(
            """
            UPDATE search_job_impressions SET last_liveness = 'closed'
            WHERE workspace_id = ? AND plan_id = ? AND job_id = ?
            """,
            [(workspace_id, plan_id, job_id) for job_id in job_ids],
        )


Clock = Callable[[], datetime]


class JobStateService:
    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self.database = database
        self.clock = clock

    def set(
        self,
        *,
        workspace_id: str,
        job_id: str,
        state: JobStateKind,
        note: str = "",
    ) -> JobState:
        value = JobState(
            workspace_id=workspace_id,
            job_id=job_id,
            state=state,
            note=note.strip(),
            updated_at=self.clock(),
        )
        with self.database.connect() as connection:
            previous = connection.execute(
                """
                SELECT state FROM job_states
                WHERE workspace_id = ? AND job_id = ?
                """,
                (value.workspace_id, value.job_id),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO job_state_events (
                    event_id, workspace_id, job_id, previous_state,
                    new_state, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"event_{uuid4().hex}",
                    value.workspace_id,
                    value.job_id,
                    previous["state"] if previous else None,
                    value.state,
                    value.note,
                    value.updated_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO job_states (
                    workspace_id, job_id, state, note, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, job_id) DO UPDATE SET
                    state = excluded.state,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (
                    value.workspace_id,
                    value.job_id,
                    value.state,
                    value.note,
                    value.updated_at.isoformat(),
                ),
            )
        return value

    def list(self, workspace_id: str) -> list[JobState]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM job_states
                WHERE workspace_id = ?
                ORDER BY updated_at DESC, job_id
                """,
                (workspace_id,),
            ).fetchall()
        return [
            JobState(
                workspace_id=row["workspace_id"],
                job_id=row["job_id"],
                state=row["state"],
                note=row["note"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]


class JobUseCase:
    def __init__(
        self,
        *,
        context: ActiveContextService,
        jobs: JobRepository,
        job_states: JobStateService,
    ) -> None:
        self.context = context
        self.jobs = jobs
        self.job_states = job_states

    def list_job_summaries(
        self,
        *,
        workspace_id: str | None = None,
        job_ids: Sequence[str] = (),
        states: Sequence[JobStateKind] = (),
        offset: int = 0,
        limit: int = 20,
    ) -> list[JobSummary]:
        workspace = self.context.resolve_workspace(workspace_id)
        jobs = self.jobs.list(workspace.workspace_id)
        if job_ids:
            selected = set(job_ids)
            jobs = [job for job in jobs if job.job_id in selected]
        if states:
            selected_states = set(states)
            state_by_job = {
                item.job_id: item.state
                for item in self.job_states.list(workspace.workspace_id)
            }
            jobs = [
                job
                for job in jobs
                if state_by_job.get(job.job_id, JobStateKind.DISCOVERED)
                in selected_states
            ]
        return [_summary(job) for job in jobs[offset : offset + limit]]

    def get_job_details(
        self,
        *,
        job_id: str,
        workspace_id: str | None = None,
    ) -> JobDetails:
        workspace = self.context.resolve_workspace(workspace_id)
        job = self.jobs.get(workspace_id=workspace.workspace_id, job_id=job_id)
        description_truncated = len(job.description) > _DESCRIPTION_LIMIT
        if description_truncated:
            job = job.model_copy(
                update={"description": job.description[:_DESCRIPTION_LIMIT]}
            )
        return JobDetails(
            job=job,
            source_records=self.jobs.source_records(
                workspace_id=workspace.workspace_id,
                job_id=job_id,
            ),
            description_truncated=description_truncated,
        )

    def update_job_state(
        self,
        *,
        workspace_id: str | None = None,
        job_id: str,
        state: JobStateKind,
        note: str = "",
    ) -> JobState:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.job_states.set(
            workspace_id=workspace.workspace_id,
            job_id=job_id,
            state=state,
            note=note,
        )

    def list_job_states(self, workspace_id: str) -> list[JobState]:
        return self.job_states.list(workspace_id)


def _summary(job) -> JobSummary:
    return JobSummary(
        job_id=job.job_id,
        title=job.title,
        company=job.company,
        locations=job.locations,
        salary=job.salary,
        recruitment_track=job.recruitment_track,
        employment_type=job.employment_type,
        apply_url=job.apply_url,
        source_name=job.source.source_name,
        liveness=job.source.liveness,
        description_excerpt=" ".join(job.description.split())[:400],
    )
