from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    DiscoverySource,
    DiscoverySourceKind,
    JobDetails,
    JobMatch,
    JobState,
    JobStateKind,
    JobSummary,
    MatchEvidence,
    SearchConfiguration,
    SearchPlan,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SearchRunResult,
    SourceRunStats,
    SourceRunStatus,
    SuggestedPlan,
    Workspace,
)
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import JobImportService
from jobfindsme.job_impressions import JobImpressionService
from jobfindsme.job_states import JobStateService
from jobfindsme.matching import DeterministicMatcher
from jobfindsme.matching.ranker import extract_job_signals, filter_jobs, score_signals
from jobfindsme.monitor_configs import MonitorConfig, MonitorConfigService
from jobfindsme.plan_suggestions import suggest_search_plan
from jobfindsme.privacy import DeletionPreview, DeletionResult, PrivacyService
from jobfindsme.profiles.models import (
    CandidateProfile,
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


class jobfindsmecore:
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
        self.matcher.stale_after_days = 7  # auto-expire UNKNOWN jobs after 7 days
        self.job_states = JobStateService(self.database)
        self.job_impressions = JobImpressionService(self.database)
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
                recruitment_track=recruitment_track,
                employment_type=employment_type,
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
                recruitment_track=recruitment_track,
                employment_type=employment_type,
                exclusions=exclusions,
            )
            self.context.activate(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
            )
        selected_sources = sources
        if sources is None and not self.source_subscriptions.list(
            workspace_id=context.workspace.workspace_id,
            plan_id=plan.plan_id,
        ):
            selected_sources = recommended_connectors(
                tuple(locations), tuple(target_roles)
            )
        elif sources is None:
            existing = self.source_subscriptions.list(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
            )
            reconciled = reconcile_catalog_sources(
                tuple(item.source for item in existing),
                locations=tuple(locations),
                roles=tuple(target_roles),
            )
            if reconciled != tuple(item.source for item in existing):
                self.source_subscriptions.replace(
                    workspace_id=context.workspace.workspace_id,
                    plan_id=plan.plan_id,
                    sources=reconciled,
                )
        subscriptions = (
            self.source_subscriptions.replace(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
                sources=selected_sources,
            )
            if selected_sources is not None
            else self.source_subscriptions.list(
                workspace_id=context.workspace.workspace_id,
                plan_id=plan.plan_id,
            )
        )
        return SearchConfiguration(
            workspace=context.workspace,
            plan=plan,
            sources=subscriptions,
            source_links=source_links(tuple(target_roles), tuple(locations)),
        )

    def suggest_plan(
        self,
        *,
        workspace_id: str | None = None,
    ) -> SuggestedPlan:
        """Derive a reviewable Search Plan proposal from confirmed facts."""
        workspace = self.context.resolve_workspace(workspace_id)
        summary = self.profiles.latest_confirmed_summary(
            workspace_id=workspace.workspace_id,
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

    def match_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        limit: int = 20,
        excluded_source_names: Sequence[str] = (),
        included_source_names: Sequence[str] = (),
    ) -> list[JobMatch]:
        """Return hard-filtered, coarse-ranked jobs with structured signals.

        Pipeline: hard filter → signal extraction → deterministic scoring
        → top-*limit* cut.  The Agent still owns semantic ranking of
        these candidates.

        If the eligible pool is ≤ *limit*, no scoring is applied —
        all pass through with score 0.0.
        """
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )
        if context.plan is None:
            raise ValueError("no active Search Plan — run configure_search first")
        profile = self.profiles.latest_confirmed_summary(
            workspace_id=context.workspace.workspace_id
        )
        jobs = self.jobs.list(context.workspace.workspace_id)
        if included_source_names:
            included = set(included_source_names)
            jobs = [job for job in jobs if job.source.source_name in included]
        if excluded_source_names:
            excluded = set(excluded_source_names)
            jobs = [job for job in jobs if job.source.source_name not in excluded]

        # filter_jobs handles scoring internally when a profile is available
        passed = filter_jobs(context.plan, jobs, profile=profile, limit=limit)
        return [
            JobMatch(
                job=job,
                score=score_signals(job, profile),
                evidence=MatchEvidence(
                    hard_filter_passed=True,
                    extracted_signals=extract_job_signals(job),
                ),
            )
            for job in passed
        ]

    def search_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        sources: tuple[DiscoverySource, ...] = (),
        limit: int = 20,
        allow_browser_sources: bool = False,
        refresh_mode: SearchRefreshMode = SearchRefreshMode.FAST,
        include_seen: bool = False,
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
        refresh_mode: SearchRefreshMode = SearchRefreshMode.FAST,
        include_seen: bool = False,
    ) -> SearchRunResult:
        """Run discovery and matching while preserving operational evidence."""

        started_at = datetime.now(UTC)
        started = perf_counter()
        context = self.context.resolve(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )
        if context.plan is None:
            raise ValueError("no active Search Plan — run configure_search first")
        effective_sources = tuple(sources) or tuple(
            item.source
            for item in self.source_subscriptions.list(
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
                error="browser source requires explicit opt-in",
            )
            for source in skipped_sources
        )
        source_runs += tuple(
            SourceRunStats(
                source_name=source.source_name,
                source_kind=source.kind,
                status=SourceRunStatus.SKIPPED,
                elapsed_seconds=0,
                error="source retired; cached historical jobs remain available",
            )
            for source in retired_sources
        )
        refresh_sources, refresh_skipped = _select_refresh_sources(
            effective_sources,
            refresh_mode,
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
                error=f"{refresh_mode} mode uses local cache for this source",
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
        )
        radar = self.job_impressions.select_and_record(
            workspace_id=context.workspace.workspace_id,
            plan_id=context.plan.plan_id,
            candidates=candidates,
            all_jobs=all_jobs,
            limit=limit,
            include_seen=include_seen,
        )
        matches = list(radar.matches)
        matching_seconds = perf_counter() - matching_started
        finished_at = datetime.now(UTC)
        total_discovered = sum(run.discovered for run in source_runs)
        total_unique = sum(run.unique for run in source_runs)
        return SearchRunResult(
            matches=tuple(matches),
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
                result_count=len(matches),
                new_count=radar.changes.new,
                changed_count=radar.changes.changed,
                reopened_count=radar.changes.reopened,
                closed_count=radar.changes.closed,
                repeated_suppressed_count=radar.changes.repeated_suppressed,
                low_relevance_filtered_count=max(
                    0,
                    self.matcher.eligible_count(context.plan, source_jobs)
                    - len(candidates),
                ),
            ),
            changes=radar.changes,
        )

    def _discover_sources(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        sources: Sequence[DiscoverySource],
        allow_browser: bool = True,
    ) -> tuple[SourceRunStats, ...]:
        import logging
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Minimize Chrome before creating background tabs
        try:
            from jobfindsme.connectors.boss_zhipin import _CDPSession

            _CDPSession.minimize_windows()
        except Exception:
            pass

        _log = logging.getLogger(__name__)
        subscriptions = {
            (item.source.kind, item.source.source_name): item
            for item in self.source_subscriptions.list(
                workspace_id=workspace_id,
                plan_id=plan_id,
            )
        }

        def _discover_one(  # noqa: E501
            source: DiscoverySource,
        ) -> SourceRunStats:
            subscription = subscriptions.get((source.kind, source.source_name))
            source_started = perf_counter()
            cached = self.jobs.has_source_jobs(
                workspace_id=workspace_id,
                source_name=source.source_name,
            )
            try:
                summary = self.discovery.discover(
                    workspace_id=workspace_id,
                    sources=(source,),
                    allow_browser=allow_browser,
                )[0]
                if source.kind.uses_browser and cached and summary.discovered == 0:
                    error = "browser refresh returned no jobs; using cached records"
                    if subscription:
                        self.source_subscriptions.record_result(
                            subscription,
                            error=error,
                            degraded=True,
                        )
                    return SourceRunStats(
                        source_name=source.source_name,
                        source_kind=source.kind,
                        status=SourceRunStatus.DEGRADED,
                        elapsed_seconds=perf_counter() - source_started,
                        cache_used=True,
                        error=error,
                    )
                # Browser sources return partial search pages — never close absent jobs
                if not source.kind.uses_browser:
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
                return SourceRunStats(
                    source_name=source.source_name,
                    source_kind=source.kind,
                    status=SourceRunStatus.SUCCESS,
                    elapsed_seconds=perf_counter() - source_started,
                    discovered=summary.discovered,
                    unique=summary.unique,
                    versions_created=summary.versions_created,
                )
            except Exception as error:
                _log.warning(
                    "source discovery failed: %s/%s — %s",
                    source.kind,
                    source.source_name,
                    error,
                )
                if cached:
                    self.jobs.mark_source_unknown(
                        workspace_id=workspace_id,
                        source_name=source.source_name,
                        observed_at=datetime.now(UTC),
                    )
                if subscription:
                    self.source_subscriptions.record_result(
                        subscription,
                        error=str(error),
                        degraded=cached,
                    )
                return SourceRunStats(
                    source_name=source.source_name,
                    source_kind=source.kind,
                    status=(
                        SourceRunStatus.DEGRADED if cached else SourceRunStatus.FAILED
                    ),
                    elapsed_seconds=perf_counter() - source_started,
                    cache_used=cached,
                    error=str(error)[:1000],
                )

        max_workers = min(len(sources), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_discover_one, source): source for source in sources
            }
            outcomes = []
            for future in as_completed(futures):
                outcome = future.result()
                outcomes.append(outcome)
                if outcome.error:
                    _log.debug(
                        "source %s/%s failed: %s",
                        outcome.source_kind,
                        outcome.source_name,
                        outcome.error,
                    )
        order = {
            (source.kind, source.source_name): index
            for index, source in enumerate(sources)
        }
        return tuple(
            sorted(
                outcomes,
                key=lambda item: order[(item.source_kind, item.source_name)],
            )
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
        schedule_cron: str | None = None,
        notification_channel: str | None = None,
    ) -> MonitorConfig:
        return self.monitor_configs.configure(
            workspace_id=workspace_id,
            plan_id=plan_id,
            enabled=enabled,
            interval_hours=interval_hours,
            schedule_cron=schedule_cron,
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
        recruitment_track=job.recruitment_track,
        employment_type=job.employment_type,
        apply_url=job.apply_url,
        source_name=job.source.source_name,
        liveness=job.source.liveness,
        description_excerpt=excerpt,
    )


def _select_refresh_sources(
    sources: tuple[DiscoverySource, ...],
    mode: SearchRefreshMode,
) -> tuple[tuple[DiscoverySource, ...], tuple[DiscoverySource, ...]]:
    """Keep interactive search quick while retaining cached broad coverage."""

    if isinstance(mode, str):
        mode = SearchRefreshMode(mode)
    if mode is SearchRefreshMode.FULL:
        return sources, ()
    if mode is SearchRefreshMode.CACHE:
        return (), sources
    preferred = tuple(
        source for source in sources if source.kind is DiscoverySourceKind.BOSS_CDP
    )
    if not preferred and sources:
        preferred = (sources[0],)
    preferred_ids = {id(source) for source in preferred}
    skipped = tuple(source for source in sources if id(source) not in preferred_ids)
    return preferred, skipped
