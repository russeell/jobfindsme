from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from jobfindsme.connectors import (
    ConnectorPolicy,
)
from jobfindsme.connectors.http import HttpTransport, UrllibTransport
from jobfindsme.contracts import (
    DiscoverySource,
    DiscoverySourceKind,
    SourceRunStats,
    SourceRunStatus,
)
from jobfindsme.importing.parsers import parse_csv, parse_json
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import ImportSummary, JobImportService
from jobfindsme.source_subscriptions import SourceSubscriptionService

_log = logging.getLogger(__name__)


def _connector_chain(
    source: DiscoverySource,
    *,
    allow_browser: bool,
) -> list[tuple[object, int]]:
    """Ordered ``(connector, enrich_limit)`` fallbacks for *source*.

    Strategy per platform — fastest first, most robust last:
    1. pure HTTP (curl_cffi, sub-second, no Chrome)   [pure_http.py]
    2. CDP DOM extraction (slowest, needs Chrome)      [china_platforms.py]

    When *allow_browser* is False the CDP fallback tier is dropped, so
    browser-free hosts still get Liepin results over pure HTTP.
    """
    from jobfindsme.connectors import ConnectorPolicy

    policy = ConnectorPolicy(public_access=True, robots_allowed=True)
    query = source.query or "AI"
    city = source.location or ""

    if source.kind in {DiscoverySourceKind.LIEPIN_HTTP, DiscoverySourceKind.LIEPIN_CDP}:
        from jobfindsme.connectors.china_platforms import LiepinConnector
        from jobfindsme.connectors.pure_http import LiepinPureHttpConnector

        chain = [
            (
                LiepinPureHttpConnector(
                    query, city=city, policy=policy, source_name=source.source_name
                ),
                0,
            ),
        ]
        if allow_browser:
            chain.append(
                (
                    LiepinConnector(
                        query, city=city, policy=policy, source_name=source.source_name
                    ),
                    3,
                )
            )
        return chain
    if source.kind is DiscoverySourceKind.ZHILIAN_HTTP:
        from jobfindsme.connectors.zhilian import (
            ZhilianCdpConnector,
            ZhilianHttpConnector,
        )

        chain = [
            (
                ZhilianHttpConnector(
                    query, city=city, policy=policy, source_name=source.source_name
                ),
                0,
            )
        ]
        if allow_browser:
            chain.append(
                (
                    ZhilianCdpConnector(
                        query, city=city, policy=policy, source_name=source.source_name
                    ),
                    3,
                )
            )
        return chain
    if source.kind is DiscoverySourceKind.WUYOU_HTTP:
        from jobfindsme.connectors.wuyou import (
            WuyouCdpConnector,
            WuyouHttpConnector,
        )

        chain = [
            (
                WuyouHttpConnector(
                    query, city=city, policy=policy, source_name=source.source_name
                ),
                0,
            )
        ]
        if allow_browser:
            chain.append(
                (
                    WuyouCdpConnector(
                        query, city=city, policy=policy, source_name=source.source_name
                    ),
                    3,
                )
            )
        return chain
    return []


class JobDiscoveryService:
    def __init__(
        self,
        imports: JobImportService,
        *,
        transport: HttpTransport | None = None,
    ) -> None:
        self.imports = imports
        self.transport = transport or UrllibTransport()

    def discover(
        self,
        *,
        workspace_id: str,
        sources: tuple[DiscoverySource, ...],
        allow_browser: bool = True,
    ) -> tuple[ImportSummary, ...]:
        return tuple(
            self._discover_one(
                workspace_id=workspace_id,
                source=source,
                allow_browser=allow_browser,
            )
            for source in sources
        )

    def _discover_one(
        self,
        *,
        workspace_id: str,
        source: DiscoverySource,
        allow_browser: bool = True,
    ) -> ImportSummary:
        if source.kind is DiscoverySourceKind.BOSS_CDP:
            from jobfindsme.connectors.boss_zhipin import BossZhipinConnector

            connector = BossZhipinConnector(
                source.query or "AI",
                city=source.location or "",
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind in {
            DiscoverySourceKind.LIEPIN_HTTP,
            DiscoverySourceKind.LIEPIN_CDP,
            DiscoverySourceKind.ZHILIAN_HTTP,
            DiscoverySourceKind.WUYOU_HTTP,
        }:
            # Walk the fallback chain: pure HTTP → CDP interception → DOM.
            # Every tier raises a typed error on transport failure; log each
            # fallback loudly — silently swallowing failures here used to
            # hide Chrome-not-running / page-changed bugs and degrade to
            # 0 jobs with no trace.
            chain = _connector_chain(source, allow_browser=allow_browser)
            last_error: Exception | None = None
            for index, (connector, enrich_limit) in enumerate(chain):
                if index > 0:
                    _log.warning(
                        "%s: %s failed (%s); falling back to %s",
                        source.source_name,
                        type(chain[index - 1][0]).__name__,
                        last_error,
                        type(connector).__name__,
                    )
                try:
                    return self.imports.import_connector(
                        workspace_id,
                        connector,
                        enrich_limit=enrich_limit,
                    )
                except Exception as error:
                    last_error = error
            raise RuntimeError(str(last_error)) from last_error
        if source.kind.retired:
            raise ValueError(f"{source.kind} is retired and cannot discover jobs")

        path = Path(source.path or "").expanduser().resolve(strict=True)
        content = path.read_text(encoding="utf-8")
        records = (
            parse_json(
                content,
                source_name=source.source_name,
                source_url=path.as_uri(),
            )
            if source.kind is DiscoverySourceKind.JSON_FILE
            else parse_csv(
                content,
                source_name=source.source_name,
                source_url=path.as_uri(),
            )
        )
        return self.imports.import_records(
            workspace_id,
            records,
            snapshot_complete=True,
        )


def refresh_sources(
    *,
    workspace_id: str,
    plan_id: str | None,
    sources: Sequence[DiscoverySource],
    allow_browser: bool,
    discovery: JobDiscoveryService,
    jobs: JobRepository,
    subscriptions: SourceSubscriptionService,
) -> tuple[SourceRunStats, ...]:
    """Execute one parallel remote refresh with per-source degradation.

    Owns connector execution, cache-aware degradation, closed-job marking,
    and source health recording; the search use case only consumes the
    resulting SourceRunStats.
    """
    try:
        from jobfindsme.connectors.boss_zhipin import _CDPSession

        _CDPSession.minimize_windows()
    except Exception:
        pass

    subscription_map = {
        (item.source.kind, item.source.source_name): item
        for item in subscriptions.list(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )
    }

    def discover_one(source: DiscoverySource) -> SourceRunStats:
        subscription = subscription_map.get((source.kind, source.source_name))
        source_started = perf_counter()
        cached = jobs.has_source_jobs(
            workspace_id=workspace_id,
            source_name=source.source_name,
        )
        try:
            summary = discovery.discover(
                workspace_id=workspace_id,
                sources=(source,),
                allow_browser=allow_browser,
            )[0]
            if source.kind.uses_browser and cached and summary.discovered == 0:
                error = "browser refresh returned no jobs; using cached records"
                if subscription:
                    subscriptions.record_result(
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
            if summary.snapshot_complete:
                jobs.mark_missing_closed(
                    workspace_id=workspace_id,
                    source_name=source.source_name,
                    observed_job_ids={job.job_id for job in summary.jobs},
                    observed_at=datetime.now(UTC),
                )
            if subscription:
                subscriptions.record_result(subscription, error=None)
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
                jobs.mark_source_unknown(
                    workspace_id=workspace_id,
                    source_name=source.source_name,
                    observed_at=datetime.now(UTC),
                )
            if subscription:
                subscriptions.record_result(
                    subscription,
                    error=str(error),
                    degraded=cached,
                )
            return SourceRunStats(
                source_name=source.source_name,
                source_kind=source.kind,
                status=(SourceRunStatus.DEGRADED if cached else SourceRunStatus.FAILED),
                elapsed_seconds=perf_counter() - source_started,
                cache_used=cached,
                error=str(error)[:1000],
            )

    with ThreadPoolExecutor(max_workers=min(len(sources), 5)) as executor:
        futures = {executor.submit(discover_one, source) for source in sources}
        outcomes = [future.result() for future in as_completed(futures)]
    order = {
        (source.kind, source.source_name): index for index, source in enumerate(sources)
    }
    return tuple(
        sorted(
            outcomes,
            key=lambda item: order[(item.source_kind, item.source_name)],
        )
    )
