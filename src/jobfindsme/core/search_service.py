"""Search use case — the user-facing "Search" concept (我找什么).

Owns plan lifecycle, source selection, the search pipeline, and the
bounded facts the Server renders in section ① of a result.
"""

from __future__ import annotations

from collections.abc import Sequence

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    DiscoverySource,
    EmploymentType,
    JobMatch,
    RecruitmentTrack,
    SalaryPolicy,
    SearchConfiguration,
    SearchPlan,
    SearchPresentationContext,
    SearchRunResult,
    Workspace,
)
from jobfindsme.core.search import SearchOrchestrator
from jobfindsme.profiles.models import FactType
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search_plans import SearchPlanService
from jobfindsme.source_catalog import (
    recommended_connectors,
    reconcile_catalog_sources,
    source_links,
)
from jobfindsme.source_subscriptions import SourceSubscriptionService


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


class SearchUseCase:
    def __init__(
        self,
        *,
        context: ActiveContextService,
        search_plans: SearchPlanService,
        profiles: ResumeProfileService,
        subscriptions: SourceSubscriptionService,
        orchestrator: SearchOrchestrator,
    ) -> None:
        self.context = context
        self.search_plans = search_plans
        self.profiles = profiles
        self.subscriptions = subscriptions
        self.orchestrator = orchestrator

    def create_workspace(self, name: str = "My Job Search") -> Workspace:
        workspace = self.context.workspaces.create(name)
        self.context.activate(workspace_id=workspace.workspace_id)
        return workspace

    def list_workspaces(self) -> list[Workspace]:
        return self.context.workspaces.list()

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

    def list_search_plans(self, workspace_id: str) -> list[SearchPlan]:
        return self.search_plans.list(workspace_id)

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

        existing = self.subscriptions.list(
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
            self.subscriptions.replace(
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

    def search_presentation_context(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        use_profile: bool = True,
    ) -> SearchPresentationContext:
        context = self.context.resolve(workspace_id=workspace_id, plan_id=plan_id)
        if context.plan is None:
            raise ValueError(
                "no active Search Plan — run setup (with target_roles) first"
            )
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
        distinct_shown, total_shows = self.orchestrator.impressions.counts(
            workspace_id=context.workspace.workspace_id,
            plan_id=context.plan.plan_id,
        )
        return SearchPresentationContext(
            profile_used=profile is not None,
            skill_count=counts[FactType.SKILL],
            project_count=counts[FactType.PROJECT],
            experience_count=counts[FactType.EXPERIENCE],
            education_count=counts[FactType.EDUCATION],
            highest_degree=highest_degree,
            applied_filters=_applied_filter_labels(context.plan),
            total_matched_count=distinct_shown,
            cumulative_shown_count=total_shows,
            closed_count=self.orchestrator.impressions.closed_count(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
            ),
        )

    # ── Search pipeline (thin delegation to the orchestrator) ─────────────

    def match_jobs(self, **kwargs) -> list[JobMatch]:
        return self.orchestrator.match_jobs(**kwargs)

    def search_jobs(self, **kwargs) -> list[JobMatch]:
        return self.orchestrator.search_jobs(**kwargs)

    def search_jobs_with_diagnostics(self, **kwargs) -> SearchRunResult:
        return self.orchestrator.search_jobs_with_diagnostics(**kwargs)
