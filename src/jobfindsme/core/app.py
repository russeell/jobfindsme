from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    DiscoverySource,
    EmploymentType,
    JobDetails,
    JobMatch,
    JobState,
    JobStateKind,
    JobSummary,
    RecruitmentTrack,
    SalaryPolicy,
    SearchConfiguration,
    SearchPlan,
    SearchPresentationContext,
    SearchRunResult,
    SuggestedPlan,
    Workspace,
)
from jobfindsme.core.search import SearchOrchestrator
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import JobImportService
from jobfindsme.job_impressions import JobImpressionService
from jobfindsme.job_states import JobStateService
from jobfindsme.plan_suggestions import suggest_search_plan
from jobfindsme.privacy import DeletionPreview, DeletionResult, PrivacyService
from jobfindsme.profiles.models import (
    CandidateProfile,
    FactType,
    ProfileSummary,
    ResumeImportMode,
)
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search_plans import SearchPlanService
from jobfindsme.source_catalog import (
    recommended_connectors,
    reconcile_catalog_sources,
    source_links,
)
from jobfindsme.source_subscriptions import SourceSubscriptionService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def _applied_filter_labels(plan: SearchPlan) -> tuple[str, ...]:
    labels = ["角色(" + "/".join(plan.target_roles) + ")"]
    if plan.locations:
        labels.append("城市(" + "/".join(plan.locations) + ")")
    if plan.salary_min_k is not None:
        labels.append(f"薪资{plan.salary_min_k}K+")
    if plan.salary_max_k is not None:
        labels.append(f"薪资不高于{plan.salary_max_k}K")
    if (
        plan.salary_min_k is not None or plan.salary_max_k is not None
    ) and plan.salary_policy is SalaryPolicy.INCLUDE_UNDISCLOSED:
        labels.append("保留薪资未公开岗位")
    if plan.experience_min_years is not None:
        labels.append(f"经验≥{plan.experience_min_years}年")
    if plan.experience_max_years is not None:
        labels.append(f"经验≤{plan.experience_max_years}年")
    if plan.recruitment_track is RecruitmentTrack.SOCIAL:
        labels.append("社招")
    elif plan.recruitment_track is RecruitmentTrack.CAMPUS:
        labels.append("校招")
    if plan.employment_type is EmploymentType.FULL_TIME:
        labels.append("正式")
    elif plan.employment_type is EmploymentType.INTERNSHIP:
        labels.append("实习")
    if plan.exclusions:
        labels.append("排除(" + "/".join(plan.exclusions) + ")")
    return tuple(labels)


class jobfindsmecore:
    """Stable, typed use-case facade shared by CLI and MCP adapters."""

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
        self.job_states = JobStateService(self.database)
        self.job_impressions = JobImpressionService(self.database)
        self.privacy = PrivacyService(self.database)
        self.source_subscriptions = SourceSubscriptionService(self.database)
        self.search = SearchOrchestrator(
            context=self.context,
            profiles=self.profiles,
            jobs=self.jobs,
            discovery=self.discovery,
            impressions=self.job_impressions,
            subscriptions=self.source_subscriptions,
        )

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
        salary_policy: str = SalaryPolicy.STRICT,
        experience_min_years: int | None = None,
        experience_max_years: int | None = None,
        recruitment_track: str | None = None,
        employment_type: str | None = None,
        exclusions: Sequence[str] = (),
    ) -> SearchPlan:
        plan = self.search_plans.create(
            workspace_id=workspace_id,
            name=name,
            target_roles=target_roles,
            locations=locations,
            salary_min_k=salary_min_k,
            salary_max_k=salary_max_k,
            salary_policy=salary_policy,
            experience_min_years=experience_min_years,
            experience_max_years=experience_max_years,
            recruitment_track=recruitment_track,
            employment_type=employment_type,
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
        salary_policy: str = SalaryPolicy.STRICT,
        experience_min_years: int | None = None,
        experience_max_years: int | None = None,
        recruitment_track: str | None = None,
        employment_type: str | None = None,
        exclusions: Sequence[str] = (),
        sources: Sequence[DiscoverySource] | None = None,
    ) -> SearchConfiguration:
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
            require_plan=False,
        )
        values = {
            "name": name,
            "target_roles": target_roles,
            "locations": locations,
            "salary_min_k": salary_min_k,
            "salary_max_k": salary_max_k,
            "salary_policy": salary_policy,
            "experience_min_years": experience_min_years,
            "experience_max_years": experience_max_years,
            "recruitment_track": recruitment_track,
            "employment_type": employment_type,
            "exclusions": exclusions,
        }
        if context.plan is None:
            plan = self.create_search_plan(
                workspace_id=context.workspace.workspace_id,
                **values,
            )
        else:
            plan = self.search_plans.update(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
                **values,
            )
            self.context.activate(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
            )

        existing = self.source_subscriptions.list(
            workspace_id=context.workspace.workspace_id,
            plan_id=plan.plan_id,
        )
        selected_sources = sources
        if sources is None and not existing:
            selected_sources = recommended_connectors(
                tuple(locations), tuple(target_roles)
            )
        elif sources is None:
            reconciled = reconcile_catalog_sources(
                tuple(item.source for item in existing),
                locations=tuple(locations),
                roles=tuple(target_roles),
            )
            if reconciled != tuple(item.source for item in existing):
                selected_sources = reconciled
        subscriptions = (
            self.source_subscriptions.replace(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
                sources=selected_sources,
            )
            if selected_sources is not None
            else existing
        )
        return SearchConfiguration(
            workspace=context.workspace,
            plan=plan,
            sources=subscriptions,
            source_links=source_links(tuple(target_roles), tuple(locations)),
        )

    def suggest_plan(self, *, workspace_id: str | None = None) -> SuggestedPlan:
        workspace = self.context.resolve_workspace(workspace_id)
        summary = self.profiles.latest_confirmed_summary(
            workspace_id=workspace.workspace_id
        )
        return suggest_search_plan(summary)

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

    def review_profile(
        self,
        *,
        profile_id: str,
        workspace_id: str | None = None,
    ) -> CandidateProfile:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.load_review(
            workspace_id=workspace.workspace_id,
            profile_id=profile_id,
        )

    def match_jobs(self, **kwargs) -> list[JobMatch]:
        return self.search.match_jobs(**kwargs)

    def search_jobs(self, **kwargs) -> list[JobMatch]:
        return self.search.search_jobs(**kwargs)

    def search_jobs_with_diagnostics(self, **kwargs) -> SearchRunResult:
        return self.search.search_jobs_with_diagnostics(**kwargs)

    def search_presentation_context(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        use_profile: bool = True,
    ) -> SearchPresentationContext:
        context = self.context.resolve(workspace_id=workspace_id, plan_id=plan_id)
        if context.plan is None:
            raise ValueError("no active Search Plan — run configure_search first")
        if use_profile:
            profile = self.profiles.latest_confirmed_summary(
                workspace_id=context.workspace.workspace_id
            )
        else:
            profile = None
        counts = {fact_type: 0 for fact_type in FactType}
        highest_degree = None
        degree_order = {"大专": 1, "本科": 2, "硕士": 3, "博士": 4}
        best_degree = 0
        if profile:
            for fact in profile.facts:
                counts[fact.fact_type] += 1
                if fact.fact_type is FactType.EDUCATION:
                    for degree, order in degree_order.items():
                        if degree in fact.value and order > best_degree:
                            highest_degree = degree
                            best_degree = order
        return SearchPresentationContext(
            profile_used=profile is not None,
            skill_count=counts[FactType.SKILL],
            project_count=counts[FactType.PROJECT],
            experience_count=counts[FactType.EXPERIENCE],
            education_count=counts[FactType.EDUCATION],
            highest_degree=highest_degree,
            applied_filters=_applied_filter_labels(context.plan),
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
        job = self.jobs.get(workspace_id=workspace.workspace_id, job_id=job_id)
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
        return self.privacy.preview_delete(workspace_id=workspace_id, scope=scope)

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
