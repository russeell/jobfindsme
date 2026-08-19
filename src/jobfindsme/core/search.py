from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from time import perf_counter

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    DiscoverySource,
    EmploymentType,
    JobMatch,
    MatchEvidence,
    RecruitmentTrack,
    SalaryPolicy,
    SearchConfiguration,
    SearchPlan,
    SearchPresentationContext,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SearchRunResult,
    SourceRunStats,
    SourceRunStatus,
    Workspace,
)
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.matching import (
    eligible_count,
    extract_job_signals,
    filter_jobs,
    has_undisclosed_salary,
    score_signals,
    undisclosed_salary_counts,
)
from jobfindsme.profiles.models import FactType
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search_plans import SearchPlanService
from jobfindsme.source_catalog import (
    recommended_connectors,
    reconcile_catalog_sources,
    source_links,
)
from jobfindsme.source_subscriptions import SourceSubscriptionService
from jobfindsme.tracking import JobImpressionService

_log = logging.getLogger(__name__)


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


class SearchOrchestrator:
    """Own the complete search use case: plans, sources, pipeline, radar."""

    def __init__(
        self,
        *,
        context: ActiveContextService,
        profiles: ResumeProfileService,
        jobs: JobRepository,
        discovery: JobDiscoveryService,
        impressions: JobImpressionService,
        subscriptions: SourceSubscriptionService,
        search_plans: SearchPlanService,
    ) -> None:
        self.context = context
        self.profiles = profiles
        self.jobs = jobs
        self.discovery = discovery
        self.impressions = impressions
        self.subscriptions = subscriptions
        self.search_plans = search_plans

    # ── Workspaces / plans ──────────────────────────────────────────────

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
        target_role: str,
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
            "target_roles": (target_role,),
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
            selected_sources = recommended_connectors(tuple(locations), (target_role,))
        elif sources is None:
            reconciled = reconcile_catalog_sources(
                tuple(item.source for item in existing),
                locations=tuple(locations),
                roles=(target_role,),
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
            preferences=plan.to_preferences(),
            sources=subscriptions,
            source_links=source_links((target_role,), tuple(locations)),
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
                "no preferences configured — run setup (with target_role) first"
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
        distinct_shown, total_shows = self.impressions.counts(
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
            closed_count=self.impressions.closed_count(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
            ),
        )

    # ── Search pipeline ─────────────────────────────────────────────────

    def match_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        limit: int = 20,
        excluded_source_names: Sequence[str] = (),
        included_source_names: Sequence[str] = (),
        use_profile: bool = True,
    ) -> list[JobMatch]:
        context = self.context.resolve(workspace_id=workspace_id, plan_id=plan_id)
        if context.plan is None:
            raise ValueError(
                "no preferences configured — run setup (with target_role) first"
            )
        if use_profile:
            profile = self.profiles.latest_confirmed_summary(
                workspace_id=context.workspace.workspace_id
            )
        else:
            profile = None
        jobs = self.jobs.list(context.workspace.workspace_id)
        if included_source_names:
            included = set(included_source_names)
            jobs = [job for job in jobs if job.source.source_name in included]
        if excluded_source_names:
            excluded = set(excluded_source_names)
            jobs = [job for job in jobs if job.source.source_name not in excluded]

        passed = filter_jobs(context.plan, jobs, profile=profile, limit=limit)
        profile_skills = (
            {
                fact.value.casefold()
                for fact in profile.facts
                if fact.fact_type is FactType.SKILL
            }
            if profile is not None
            else set()
        )
        matches = []
        for job in passed:
            signals = extract_job_signals(job)
            required_skills = signals["required_skills"]
            matched = [
                skill for skill in required_skills if skill.casefold() in profile_skills
            ]
            missing = [
                skill
                for skill in required_skills
                if skill.casefold() not in profile_skills
            ]
            matches.append(
                JobMatch(
                    job=job,
                    score=score_signals(job, profile),
                    evidence=MatchEvidence(
                        hard_filter_passed=True,
                        matched_profile_skills=tuple(matched),
                        missing_required_skills=tuple(missing),
                        warnings=(
                            ("薪资未公开，尚未验证是否满足薪资条件",)
                            if has_undisclosed_salary(job)
                            and (
                                context.plan.salary_min_k is not None
                                or context.plan.salary_max_k is not None
                            )
                            else ()
                        ),
                        extracted_signals=signals,
                    ),
                )
            )
        return matches

    def search_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        sources: tuple[DiscoverySource, ...] = (),
        limit: int = 20,
        allow_browser_sources: bool = False,
        refresh_mode: SearchRefreshMode = SearchRefreshMode.LIVE,
        include_seen: bool = False,
        use_profile: bool = True,
    ) -> list[JobMatch]:
        return list(
            self.search_jobs_with_diagnostics(
                workspace_id=workspace_id,
                plan_id=plan_id,
                sources=sources,
                limit=limit,
                allow_browser_sources=allow_browser_sources,
                refresh_mode=refresh_mode,
                include_seen=include_seen,
                use_profile=use_profile,
            ).matches
        )

    def search_jobs_with_diagnostics(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        sources: tuple[DiscoverySource, ...] = (),
        limit: int = 20,
        allow_browser_sources: bool = False,
        refresh_mode: SearchRefreshMode = SearchRefreshMode.LIVE,
        include_seen: bool = False,
        use_profile: bool = True,
    ) -> SearchRunResult:
        started_at = datetime.now(UTC)
        started = perf_counter()
        context = self.context.resolve(workspace_id=workspace_id, plan_id=plan_id)
        if context.plan is None:
            raise ValueError(
                "no preferences configured — run setup (with target_role) first"
            )

        effective_sources = tuple(sources) or tuple(
            item.source
            for item in self.subscriptions.list(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
            )
        )
        retired_sources = tuple(
            source for source in effective_sources if source.kind.retired
        )
        effective_sources = tuple(
            source for source in effective_sources if not source.kind.retired
        )
        active_source_names = tuple(
            dict.fromkeys(source.source_name for source in effective_sources)
        )

        skipped_sources: tuple[DiscoverySource, ...] = ()
        if not allow_browser_sources:
            skipped_sources = tuple(
                source for source in effective_sources if source.kind.uses_browser
            )
            browser_source_names = {source.source_name for source in skipped_sources}
            effective_sources = tuple(
                source for source in effective_sources if not source.kind.uses_browser
            )
        else:
            browser_source_names = set()

        source_runs = tuple(
            SourceRunStats(
                source_name=source.source_name,
                source_kind=source.kind,
                status=SourceRunStatus.SKIPPED,
                elapsed_seconds=0,
                error="浏览器来源需显式开启",
            )
            for source in skipped_sources
        )
        source_runs += tuple(
            SourceRunStats(
                source_name=source.source_name,
                source_kind=source.kind,
                status=SourceRunStatus.SKIPPED,
                elapsed_seconds=0,
                error="来源已停用，历史岗位仍可检索",
            )
            for source in retired_sources
        )
        refresh_sources, refresh_skipped = select_refresh_sources(
            effective_sources, refresh_mode
        )
        source_runs += tuple(
            SourceRunStats(
                source_name=source.source_name,
                source_kind=source.kind,
                status=SourceRunStatus.SKIPPED,
                elapsed_seconds=0,
                cache_used=self.jobs.has_source_jobs(
                    workspace_id=context.workspace.workspace_id,
                    source_name=source.source_name,
                ),
                error="缓存模式未刷新",
            )
            for source in refresh_skipped
        )
        if refresh_sources:
            source_runs += self._discover_sources(
                workspace_id=context.workspace.workspace_id,
                plan_id=context.plan.plan_id,
                sources=refresh_sources,
                allow_browser=allow_browser_sources,
            )

        matching_started = perf_counter()
        all_jobs = self.jobs.list(context.workspace.workspace_id)
        source_jobs = all_jobs
        if active_source_names:
            included = set(active_source_names)
            source_jobs = [
                job for job in source_jobs if job.source.source_name in included
            ]
        if browser_source_names:
            source_jobs = [
                job
                for job in source_jobs
                if job.source.source_name not in browser_source_names
            ]
        candidate_limit = max(100, limit * 5, len(source_jobs))
        candidates = self.match_jobs(
            workspace_id=context.workspace.workspace_id,
            plan_id=context.plan.plan_id,
            limit=candidate_limit,
            excluded_source_names=tuple(browser_source_names),
            included_source_names=active_source_names,
            use_profile=use_profile,
        )
        radar = self.impressions.select_and_record(
            workspace_id=context.workspace.workspace_id,
            plan_id=context.plan.plan_id,
            candidates=candidates,
            all_jobs=all_jobs,
            limit=limit,
            include_seen=include_seen,
        )
        matching_seconds = perf_counter() - matching_started
        finished_at = datetime.now(UTC)
        total_discovered = sum(run.discovered for run in source_runs)
        total_unique = sum(run.unique for run in source_runs)
        salary_filtered, salary_included = undisclosed_salary_counts(
            context.plan, source_jobs
        )
        return SearchRunResult(
            matches=radar.matches,
            diagnostics=SearchRunDiagnostics(
                started_at=started_at,
                finished_at=finished_at,
                elapsed_seconds=perf_counter() - started,
                matching_seconds=matching_seconds,
                refresh_mode=refresh_mode,
                source_runs=source_runs,
                total_discovered=total_discovered,
                total_unique=total_unique,
                duplicates_removed=max(0, total_discovered - total_unique),
                result_count=len(radar.matches),
                new_count=radar.changes.new,
                changed_count=radar.changes.changed,
                reopened_count=radar.changes.reopened,
                closed_count=radar.changes.closed,
                repeated_suppressed_count=radar.changes.repeated_suppressed,
                low_relevance_filtered_count=max(
                    0,
                    eligible_count(context.plan, source_jobs) - len(candidates),
                ),
                undisclosed_salary_filtered_count=salary_filtered,
                undisclosed_salary_included_count=salary_included,
            ),
            changes=radar.changes,
        )

    def _discover_sources(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        sources: Sequence[DiscoverySource],
        allow_browser: bool = True,
    ) -> tuple[SourceRunStats, ...]:
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
            require_plan=False,
        )
        from jobfindsme.importing.discovery import refresh_sources

        return refresh_sources(
            workspace_id=context.workspace.workspace_id,
            plan_id=context.plan.plan_id if context.plan else None,
            sources=sources,
            allow_browser=allow_browser,
            discovery=self.discovery,
            jobs=self.jobs,
            subscriptions=self.subscriptions,
        )


def select_refresh_sources(
    sources: tuple[DiscoverySource, ...],
    mode: SearchRefreshMode,
) -> tuple[tuple[DiscoverySource, ...], tuple[DiscoverySource, ...]]:
    if isinstance(mode, str):
        mode = SearchRefreshMode(mode)
    if mode is SearchRefreshMode.CACHE:
        return (), sources
    # LIVE (and deprecated FAST/FULL aliases) refresh all maintained sources
    # concurrently. Per-source failures are isolated, so one challenged
    # platform never blocks results from others.
    return sources, ()
