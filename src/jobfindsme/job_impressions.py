from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from jobfindsme.contracts import (
    JobChangeType,
    JobLiveness,
    JobMatch,
    JobPosting,
    JobStateKind,
    SearchChanges,
)
from jobfindsme.storage import Database


@dataclass(frozen=True)
class RadarSelection:
    matches: tuple[JobMatch, ...]
    changes: SearchChanges


class JobImpressionService:
    """Persist what one Search Plan has actually shown to the user."""

    def __init__(self, database: Database) -> None:
        self.database = database

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
