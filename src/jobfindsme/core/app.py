from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    DiscoverySource,
    JobDetails,
    JobMatch,
    JobState,
    JobStateKind,
    JobSummary,
    SearchConfiguration,
    SearchPlan,
    Workspace,
)
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import JobImportService
from jobfindsme.job_states import JobStateService
from jobfindsme.matching import DeterministicMatcher
from jobfindsme.monitor_configs import MonitorConfig, MonitorConfigService
from jobfindsme.privacy import DeletionPreview, DeletionResult, PrivacyService
from jobfindsme.profiles.models import (
    CandidateProfile,
    ProfileSummary,
    ResumeImportMode,
)
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search_plans import SearchPlanService
from jobfindsme.source_subscriptions import SourceSubscriptionService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


class JobFindsMeCore:
    """Typed use-case API shared by every adapter."""

    def __init__(self, database_path: str | Path) -> None:
        self.database = Database(database_path)
        self.database.migrate()
        self.workspaces = WorkspaceService(self.database)
        self.search_plans = SearchPlanService(self.database)
        self.context = ActiveContextService(
            self.database,
            self.workspaces,
            self.search_plans,
        )
        self.profiles = ResumeProfileService(self.database)
        self.jobs = JobRepository(self.database)
        self.job_imports = JobImportService(self.jobs)
        self.discovery = JobDiscoveryService(self.job_imports)
        self.matcher = DeterministicMatcher()
        self.job_states = JobStateService(self.database)
        self.privacy = PrivacyService(self.database)
        self.monitor_configs = MonitorConfigService(self.database)
        self.source_subscriptions = SourceSubscriptionService(self.database)

    def create_workspace(self, name: str = "My Job Search") -> Workspace:
        workspace = self.workspaces.create(name)
        self.context.activate(workspace_id=workspace.workspace_id)
        return workspace

    def list_workspaces(self) -> list[Workspace]:
        return self.workspaces.list()

    def create_search_plan(
        self,
        *,
        workspace_id: str,
        name: str,
        target_roles: Sequence[str],
        locations: Sequence[str] = (),
        salary_min_k: int | None = None,
        salary_max_k: int | None = None,
        experience_min_years: int | None = None,
        experience_max_years: int | None = None,
        exclusions: Sequence[str] = (),
    ) -> SearchPlan:
        plan = self.search_plans.create(
            workspace_id=workspace_id,
            name=name,
            target_roles=target_roles,
            locations=locations,
            salary_min_k=salary_min_k,
            salary_max_k=salary_max_k,
            experience_min_years=experience_min_years,
            experience_max_years=experience_max_years,
            exclusions=exclusions,
        )
        self.context.activate(workspace_id=workspace_id, plan_id=plan.plan_id)
        return plan

    def configure_search(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        name: str = "Default Search",
        target_roles: Sequence[str],
        locations: Sequence[str] = (),
        salary_min_k: int | None = None,
        salary_max_k: int | None = None,
        experience_min_years: int | None = None,
        experience_max_years: int | None = None,
        exclusions: Sequence[str] = (),
        sources: Sequence[DiscoverySource] | None = None,
    ) -> SearchConfiguration:
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
            require_plan=False,
        )
        if context.plan is None:
            plan = self.create_search_plan(
                workspace_id=context.workspace.workspace_id,
                name=name,
                target_roles=target_roles,
                locations=locations,
                salary_min_k=salary_min_k,
                salary_max_k=salary_max_k,
                experience_min_years=experience_min_years,
                experience_max_years=experience_max_years,
                exclusions=exclusions,
            )
        else:
            plan = self.search_plans.update(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
                name=name,
                target_roles=target_roles,
                locations=locations,
                salary_min_k=salary_min_k,
                salary_max_k=salary_max_k,
                experience_min_years=experience_min_years,
                experience_max_years=experience_max_years,
                exclusions=exclusions,
            )
            self.context.activate(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
            )
        subscriptions = (
            self.source_subscriptions.replace(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
                sources=sources,
            )
            if sources is not None
            else self.source_subscriptions.list(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
            )
        )
        return SearchConfiguration(
            workspace=context.workspace,
            plan=plan,
            sources=subscriptions,
        )

    def list_search_plans(self, workspace_id: str) -> list[SearchPlan]:
        return self.search_plans.list(workspace_id)

    def import_resume(
        self,
        *,
        workspace_id: str | None = None,
        source_path: str | Path,
        mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE,
    ) -> CandidateProfile:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.import_resume(
            workspace_id=workspace.workspace_id,
            source_path=source_path,
            mode=mode,
        )

    def confirm_profile(
        self,
        *,
        workspace_id: str | None = None,
        profile_id: str,
        accepted_fact_ids: Sequence[str],
        corrections: Mapping[str, str] | None = None,
    ) -> ProfileSummary:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.confirm_profile(
            workspace_id=workspace.workspace_id,
            profile_id=profile_id,
            accepted_fact_ids=accepted_fact_ids,
            corrections=corrections,
        )

    def match_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        limit: int = 20,
    ) -> list[JobMatch]:
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )
        assert context.plan is not None
        profile = self.profiles.latest_confirmed_summary(
            workspace_id=context.workspace.workspace_id
        )
        return self.matcher.match(
            context.plan,
            self.jobs.list(context.workspace.workspace_id),
            profile=profile,
            limit=limit,
        )

    def search_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        sources: tuple[DiscoverySource, ...] = (),
        limit: int = 20,
    ) -> list[JobMatch]:
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )
        assert context.plan is not None
        effective_sources = tuple(sources) or tuple(
            item.source
            for item in self.source_subscriptions.list(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
            )
        )
        if effective_sources:
            self._discover_sources(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
                sources=effective_sources,
            )
        return self.match_jobs(
            workspace_id=context.workspace.workspace_id,
            plan_id=context.plan.plan_id,
            limit=limit,
        )

    def _discover_sources(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        sources: Sequence[DiscoverySource],
    ) -> None:
        subscriptions = {
            (item.source.kind, item.source.source_name): item
            for item in self.source_subscriptions.list(
                workspace_id=workspace_id,
                plan_id=plan_id,
            )
        }
        failures: list[str] = []
        successful = 0
        for source in sources:
            subscription = subscriptions.get((source.kind, source.source_name))
            try:
                summary = self.discovery.discover(
                    workspace_id=workspace_id,
                    sources=(source,),
                )[0]
                successful += 1
                self.jobs.mark_missing_closed(
                    workspace_id=workspace_id,
                    source_name=source.source_name,
                    observed_job_ids={job.job_id for job in summary.jobs},
                    observed_at=datetime.now(UTC),
                )
                if subscription:
                    self.source_subscriptions.record_result(
                        subscription,
                        error=None,
                    )
            except Exception as error:
                failures.append(f"{source.source_name}: {error}")
                if subscription:
                    self.source_subscriptions.record_result(
                        subscription,
                        error=str(error),
                    )
        if sources and successful == 0:
            raise RuntimeError("all job sources failed: " + "; ".join(failures))

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

    def export_local_data(self, workspace_id: str) -> dict[str, object]:
        return self.privacy.export_workspace(workspace_id)

    def export_local_file(self, workspace_id: str | None = None):
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.export_workspace_to_file(workspace.workspace_id)

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
        job = self.jobs.get(
            workspace_id=workspace.workspace_id,
            job_id=job_id,
        )
        description_truncated = len(job.description) > 20_000
        if description_truncated:
            job = job.model_copy(update={"description": job.description[:20_000]})
        return JobDetails(
            job=job,
            source_records=self.jobs.source_records(
                workspace_id=workspace.workspace_id,
                job_id=job_id,
            ),
            description_truncated=description_truncated,
        )

    def preview_delete(self, *, workspace_id: str, scope: str) -> DeletionPreview:
        return self.privacy.preview_delete(
            workspace_id=workspace_id,
            scope=scope,
        )

    def confirm_delete(
        self,
        *,
        workspace_id: str,
        scope: str,
        confirmation_token: str,
    ) -> DeletionResult:
        return self.privacy.confirm_delete(
            workspace_id=workspace_id,
            scope=scope,
            confirmation_token=confirmation_token,
        )

    def configure_monitor(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        enabled: bool,
        interval_hours: int = 24,
        notification_channel: str | None = None,
    ) -> MonitorConfig:
        return self.monitor_configs.configure(
            workspace_id=workspace_id,
            plan_id=plan_id,
            enabled=enabled,
            interval_hours=interval_hours,
            notification_channel=notification_channel,
        )


def _summary(job) -> JobSummary:
    excerpt = " ".join(job.description.split())[:400]
    return JobSummary(
        job_id=job.job_id,
        title=job.title,
        company=job.company,
        locations=job.locations,
        salary=job.salary,
        apply_url=job.apply_url,
        source_name=job.source.source_name,
        liveness=job.source.liveness,
        description_excerpt=excerpt,
    )
