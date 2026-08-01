"""jobfindsmecore — a very thin application-core facade.

The facade wires domain services and exposes stable use-case methods to
the CLI and MCP adapters.  It contains NO business logic — each method
delegates to the matching use case:

    ProfileUseCase  — profiles/ (resume → facts → suggested plan)
    SearchUseCase   — plans, sources, search pipeline, presentation facts
    JobUseCase      — summaries, details, user state
    PrivacyUseCase  — export and two-phase deletion

Dependency direction: CLI / MCP → core → domain services → storage /
connectors.  Adapters never touch repositories directly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    JobDetails,
    JobMatch,
    JobState,
    JobSummary,
    SearchConfiguration,
    SearchPlan,
    SearchPresentationContext,
    SearchRunResult,
    SuggestedPlan,
    Workspace,
)
from jobfindsme.core.job_service import JobUseCase
from jobfindsme.core.privacy_service import PrivacyUseCase
from jobfindsme.core.profile_service import ProfileUseCase
from jobfindsme.core.search import SearchOrchestrator
from jobfindsme.core.search_service import SearchUseCase
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import JobImportService
from jobfindsme.job_impressions import JobImpressionService
from jobfindsme.job_states import JobStateService
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


class jobfindsmecore:
    """Stable, typed use-case facade shared by CLI and MCP adapters."""

    def __init__(self, database_path: str | Path) -> None:
        self.database = Database(database_path)
        self.database.migrate()
        workspaces = WorkspaceService(self.database)
        search_plans = SearchPlanService(self.database)
        self.context = ActiveContextService(
            self.database,
            workspaces,
            search_plans,
        )
        profiles = ResumeProfileService(self.database)
        jobs = JobRepository(self.database)
        job_imports = JobImportService(jobs)
        discovery = JobDiscoveryService(job_imports)
        job_states = JobStateService(self.database)
        job_impressions = JobImpressionService(self.database)
        privacy = PrivacyService(self.database)
        subscriptions = SourceSubscriptionService(self.database)
        orchestrator = SearchOrchestrator(
            context=self.context,
            profiles=profiles,
            jobs=jobs,
            discovery=discovery,
            impressions=job_impressions,
            subscriptions=subscriptions,
        )

        # Domain services referenced by tests and the doctor.
        self.workspaces = workspaces
        self.search_plans = search_plans
        self.profiles = profiles
        self.jobs = jobs
        self.job_imports = job_imports
        self.discovery = discovery
        self.job_states = job_states
        self.job_impressions = job_impressions
        self.privacy = privacy
        self.source_subscriptions = subscriptions
        self.search = orchestrator

        # Use cases — the actual application layer.
        self.profile_use_case = ProfileUseCase(
            context=self.context,
            profiles=profiles,
        )
        self.search_use_case = SearchUseCase(
            context=self.context,
            search_plans=search_plans,
            profiles=profiles,
            subscriptions=subscriptions,
            orchestrator=orchestrator,
        )
        self.job_use_case = JobUseCase(
            context=self.context,
            jobs=jobs,
            job_states=job_states,
        )
        self.privacy_use_case = PrivacyUseCase(
            context=self.context,
            privacy=privacy,
        )

    # ── Workspaces / plans ─────────────────────────────────────────────────

    def create_workspace(self, name: str = "My Job Search") -> Workspace:
        return self.search_use_case.create_workspace(name)

    def list_workspaces(self) -> list[Workspace]:
        return self.search_use_case.list_workspaces()

    def create_search_plan(self, **kwargs) -> SearchPlan:
        return self.search_use_case.create_search_plan(**kwargs)

    def configure_search(self, **kwargs) -> SearchConfiguration:
        return self.search_use_case.configure_search(**kwargs)

    def list_search_plans(self, workspace_id: str) -> list[SearchPlan]:
        return self.search_use_case.list_search_plans(workspace_id)

    # ── Profile ────────────────────────────────────────────────────────────

    def import_resume(
        self,
        *,
        workspace_id: str | None = None,
        source_path: str | Path,
        mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE,
    ) -> CandidateProfile:
        return self.profile_use_case.import_resume(
            workspace_id=workspace_id,
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
        return self.profile_use_case.confirm_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
            accepted_fact_ids=accepted_fact_ids,
            corrections=corrections,
        )

    def review_profile(
        self,
        *,
        profile_id: str,
        workspace_id: str | None = None,
    ) -> CandidateProfile:
        return self.profile_use_case.review_profile(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )

    def suggest_plan(self, *, workspace_id: str | None = None) -> SuggestedPlan:
        return self.profile_use_case.suggest_plan(workspace_id=workspace_id)

    # ── Search ─────────────────────────────────────────────────────────────

    def match_jobs(self, **kwargs) -> list[JobMatch]:
        return self.search_use_case.match_jobs(**kwargs)

    def search_jobs(self, **kwargs) -> list[JobMatch]:
        return self.search_use_case.search_jobs(**kwargs)

    def search_jobs_with_diagnostics(self, **kwargs) -> SearchRunResult:
        return self.search_use_case.search_jobs_with_diagnostics(**kwargs)

    def search_presentation_context(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        use_profile: bool = True,
    ) -> SearchPresentationContext:
        return self.search_use_case.search_presentation_context(
            workspace_id=workspace_id,
            plan_id=plan_id,
            use_profile=use_profile,
        )

    # ── Jobs / tracking ────────────────────────────────────────────────────

    def list_job_summaries(self, **kwargs) -> list[JobSummary]:
        return self.job_use_case.list_job_summaries(**kwargs)

    def get_job_details(self, **kwargs) -> JobDetails:
        return self.job_use_case.get_job_details(**kwargs)

    def update_job_state(self, **kwargs) -> JobState:
        return self.job_use_case.update_job_state(**kwargs)

    def list_job_states(self, workspace_id: str) -> list[JobState]:
        return self.job_use_case.list_job_states(workspace_id)

    # ── Privacy ────────────────────────────────────────────────────────────

    def export_local_data(self, workspace_id: str) -> dict[str, object]:
        return self.privacy_use_case.export_local_data(workspace_id)

    def export_local_file(self, workspace_id: str | None = None):
        return self.privacy_use_case.export_local_file(workspace_id)

    def preview_delete(
        self,
        *,
        workspace_id: str,
        scope: str,
    ) -> DeletionPreview:
        return self.privacy_use_case.preview_delete(
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
        return self.privacy_use_case.confirm_delete(
            workspace_id=workspace_id,
            scope=scope,
            confirmation_token=confirmation_token,
        )
