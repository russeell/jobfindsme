from __future__ import annotations

import logging
from pathlib import Path

from jobfindsme.connectors import (
    ConnectorPolicy,
)
from jobfindsme.connectors.http import HttpTransport, UrllibTransport
from jobfindsme.contracts import DiscoverySource, DiscoverySourceKind
from jobfindsme.importing.parsers import parse_csv, parse_json
from jobfindsme.importing.service import ImportSummary, JobImportService

_log = logging.getLogger(__name__)


def _connector_chain(
    source: DiscoverySource,
) -> list[tuple[object, int]]:
    """Ordered ``(connector, enrich_limit)`` fallbacks for *source*.

    Strategy per platform — fastest first, most robust last:
    1. pure HTTP (curl_cffi, sub-second, no Chrome)   [pure_http.py]
    2. CDP DOM extraction (slowest, needs Chrome)      [china_platforms.py]
    """
    from jobfindsme.connectors import ConnectorPolicy

    policy = ConnectorPolicy(public_access=True, robots_allowed=True)
    query = source.query or "AI"
    city = source.location or ""

    if source.kind is DiscoverySourceKind.LIEPIN_CDP:
        from jobfindsme.connectors.china_platforms import LiepinConnector
        from jobfindsme.connectors.pure_http import LiepinPureHttpConnector

        return [
            (
                LiepinPureHttpConnector(
                    query, city=city, policy=policy, source_name=source.source_name
                ),
                0,
            ),
            (
                LiepinConnector(
                    query, city=city, policy=policy, source_name=source.source_name
                ),
                3,
            ),
        ]
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
    ) -> tuple[ImportSummary, ...]:
        return tuple(
            self._discover_one(workspace_id=workspace_id, source=source)
            for source in sources
        )

    def _discover_one(
        self,
        *,
        workspace_id: str,
        source: DiscoverySource,
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
        if source.kind is DiscoverySourceKind.LIEPIN_CDP:
            # Walk the fallback chain: pure HTTP → CDP interception → DOM.
            # Every tier raises a typed error on transport failure; log each
            # fallback loudly — silently swallowing failures here used to
            # hide Chrome-not-running / page-changed bugs and degrade to
            # 0 jobs with no trace.
            chain = _connector_chain(source)
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
            raise RuntimeError(
                f"all connectors failed for {source.source_name}"
            ) from last_error
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
        return self.imports.import_records(workspace_id, records)
