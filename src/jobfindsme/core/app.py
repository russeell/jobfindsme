from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from jobfindsme.contracts import (
    JobMatch,
    JobState,
    JobStateKind,
    SearchPlan,
    Workspace,
)
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
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


class JobFindsMeCore:
    """Typed use-case API shared by every adapter."""

    def __init__(self, database_path: str | Path) -> None:
        self.database = Database(database_path)
        self.database.migrate()
        self.workspaces = WorkspaceService(self.database)
        self.search_plans = SearchPlanService(self.database)
        self.profiles = ResumeProfileService(self.database)
        self.jobs = JobRepository(self.database)
        self.job_imports = JobImportService(self.jobs)
        self.matcher = DeterministicMatcher()
        self.job_states = JobStateService(self.database)
        self.privacy = PrivacyService(self.database)
        self.monitor_configs = MonitorConfigService(self.database)

    def create_workspace(self, name: str = "My Job Search") -> Workspace:
        return self.workspaces.create(name)

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
        return self.search_plans.create(
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

    def list_search_plans(self, workspace_id: str) -> list[SearchPlan]:
        return self.search_plans.list(workspace_id)

    def import_resume(
        self,
        *,
        workspace_id: str,
        source_path: str | Path,
        mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE,
    ) -> CandidateProfile:
        return self.profiles.import_resume(
            workspace_id=workspace_id,
            source_path=source_path,
            mode=mode,
        )

    def confirm_profile(
        self,
        *,
        workspace_id: str,
        profile_id: str,
        accepted_fact_ids: Sequence[str],
        corrections: Mapping[str, str] | None = None,
    ) -> ProfileSummary:
        return self.profiles.confirm_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
            accepted_fact_ids=accepted_fact_ids,
            corrections=corrections,
        )

    def match_jobs(
        self, *, workspace_id: str, plan_id: str, limit: int = 20
    ) -> list[JobMatch]:
        plan = self.search_plans.get(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )
        return self.matcher.match(plan, self.jobs.list(workspace_id), limit=limit)

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
