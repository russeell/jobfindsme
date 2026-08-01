"""Job use case — the user-facing "Job / Tracking" concepts (找到了什么、跟踪).

Owns job summaries, full details, and user state (applied / saved /
rejected).  Full JD text is only served one job at a time so a search
result never blows up the host context.
"""

from __future__ import annotations

from collections.abc import Sequence

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    JobDetails,
    JobState,
    JobStateKind,
    JobSummary,
)
from jobfindsme.importing.repository import JobRepository
from jobfindsme.job_states import JobStateService

_DESCRIPTION_LIMIT = 20_000


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
                job for job in jobs if state_by_job.get(job.job_id) in selected_states
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
        workspace_id: str,
        job_id: str,
        state: JobStateKind,
        note: str = "",
    ) -> JobState:
        return self.job_states.set(
            workspace_id=workspace_id,
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
