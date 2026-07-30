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


def _try_http_connector(
    source: DiscoverySource,
) -> object | None:
    """Return an HTTP-based connector for *source*, or None to use DOM."""
    from jobfindsme.connectors import ConnectorPolicy

    policy = ConnectorPolicy(public_access=True, robots_allowed=True)
    if source.kind is DiscoverySourceKind.WUYOU_CDP:
        from jobfindsme.connectors.http_platforms import (
            WuyouHttpConnector,
        )

        return WuyouHttpConnector(
            source.query or "AI",
            city=source.location or "",
            policy=policy,
            source_name=source.source_name,
        )
    if source.kind is DiscoverySourceKind.ZHILIAN_CDP:
        from jobfindsme.connectors.http_platforms import (
            ZhilianHttpConnector,
        )

        return ZhilianHttpConnector(
            source.query or "AI",
            city=source.location or "",
            policy=policy,
            source_name=source.source_name,
        )
    return None


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
        if source.kind in {
            DiscoverySourceKind.LIEPIN_CDP,
            DiscoverySourceKind.ZHILIAN_CDP,
            DiscoverySourceKind.WUYOU_CDP,
        }:
            from jobfindsme.connectors.china_platforms import (
                LiepinConnector,
                WuyouConnector,
                ZhilianConnector,
            )

            connector_cls = {
                DiscoverySourceKind.LIEPIN_CDP: LiepinConnector,
                DiscoverySourceKind.ZHILIAN_CDP: ZhilianConnector,
                DiscoverySourceKind.WUYOU_CDP: WuyouConnector,
            }[source.kind]

            # Try HTTP connector first (structured JSON, no DOM regex).
            # On transport failure (InterceptionFailedError etc.) fall back
            # to the DOM connector — but log it; silently swallowing HTTP
            # failures here used to hide Chrome-not-running / page-changed
            # bugs and silently degrade to 0 jobs.
            http_connector = _try_http_connector(source)
            if http_connector is not None:
                try:
                    return self.imports.import_connector(workspace_id, http_connector)
                except Exception as error:
                    _log.warning(
                        "HTTP connector for %s failed (%s); falling back to DOM",
                        source.source_name,
                        error,
                    )

            connector = connector_cls(
                source.query or "AI",
                city=source.location or "",
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            enrich_limit = (
                3
                if source.kind
                in {
                    DiscoverySourceKind.LIEPIN_CDP,
                    DiscoverySourceKind.ZHILIAN_CDP,
                }
                else 0
            )
            return self.imports.import_connector(
                workspace_id,
                connector,
                enrich_limit=enrich_limit,
            )
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
