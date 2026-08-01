from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from time import perf_counter

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import (
    DiscoverySource,
    JobMatch,
    MatchEvidence,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SearchRunResult,
    SourceRunStats,
    SourceRunStatus,
)
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.job_impressions import JobImpressionService
from jobfindsme.matching.ranker import (
    eligible_count,
    extract_job_signals,
    filter_jobs,
    has_undisclosed_salary,
    score_signals,
    undisclosed_salary_counts,
)
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.source_subscriptions import SourceSubscriptionService

_log = logging.getLogger(__name__)


class SearchOrchestrator:
    """Own the online search use case without exposing adapter concerns."""

    def __init__(
        self,
        *,
        context: ActiveContextService,
        profiles: ResumeProfileService,
        jobs: JobRepository,
        discovery: JobDiscoveryService,
        impressions: JobImpressionService,
        subscriptions: SourceSubscriptionService,
    ) -> None:
        self.context = context
        self.profiles = profiles
        self.jobs = jobs
        self.discovery = discovery
        self.impressions = impressions
        self.subscriptions = subscriptions

    def match_jobs(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        limit: int = 20,
        excluded_source_names: Sequence[str] = (),
        included_source_names: Sequence[str] = (),
    ) -> list[JobMatch]:
        context = self.context.resolve(workspace_id=workspace_id, plan_id=plan_id)
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

        passed = filter_jobs(context.plan, jobs, profile=profile, limit=limit)
        return [
            JobMatch(
                job=job,
                score=score_signals(job, profile),
                evidence=MatchEvidence(
                    hard_filter_passed=True,
                    warnings=(
                        ("薪资未公开，尚未验证是否满足薪资条件",)
                        if has_undisclosed_salary(job)
                        and (
                            context.plan.salary_min_k is not None
                            or context.plan.salary_max_k is not None
                        )
                        else ()
                    ),
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
        started_at = datetime.now(UTC)
        started = perf_counter()
        context = self.context.resolve(workspace_id=workspace_id, plan_id=plan_id)
        if context.plan is None:
            raise ValueError("no active Search Plan — run configure_search first")

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
        workspace_id: str,
        plan_id: str,
        sources: Sequence[DiscoverySource],
        allow_browser: bool = True,
    ) -> tuple[SourceRunStats, ...]:
        try:
            from jobfindsme.connectors.boss_zhipin import _CDPSession

            _CDPSession.minimize_windows()
        except Exception:
            pass

        subscriptions = {
            (item.source.kind, item.source.source_name): item
            for item in self.subscriptions.list(
                workspace_id=workspace_id,
                plan_id=plan_id,
            )
        }

        def discover_one(source: DiscoverySource) -> SourceRunStats:
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
                        self.subscriptions.record_result(
                            subscription, error=error, degraded=True
                        )
                    return SourceRunStats(
                        source_name=source.source_name,
                        source_kind=source.kind,
                        status=SourceRunStatus.DEGRADED,
                        elapsed_seconds=perf_counter() - source_started,
                        cache_used=True,
                        error=error,
                    )
                if not source.kind.uses_browser:
                    self.jobs.mark_missing_closed(
                        workspace_id=workspace_id,
                        source_name=source.source_name,
                        observed_job_ids={job.job_id for job in summary.jobs},
                        observed_at=datetime.now(UTC),
                    )
                if subscription:
                    self.subscriptions.record_result(subscription, error=None)
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
                    self.subscriptions.record_result(
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

        with ThreadPoolExecutor(max_workers=min(len(sources), 5)) as executor:
            futures = {executor.submit(discover_one, source) for source in sources}
            outcomes = [future.result() for future in as_completed(futures)]
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


def select_refresh_sources(
    sources: tuple[DiscoverySource, ...],
    mode: SearchRefreshMode,
) -> tuple[tuple[DiscoverySource, ...], tuple[DiscoverySource, ...]]:
    if isinstance(mode, str):
        mode = SearchRefreshMode(mode)
    if mode is SearchRefreshMode.FULL:
        return sources, ()
    if mode is SearchRefreshMode.CACHE:
        return (), sources
    # The maintained catalog contains only two bounded sources. Refreshing
    # both concurrently is faster and more reliable than making BOSS a
    # single-source gate: Liepin can still return when browser state degrades.
    return sources, ()
