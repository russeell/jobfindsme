from __future__ import annotations

from pathlib import Path

from jobfindsme.connectors import (
    ConnectorPolicy,
)
from jobfindsme.connectors.http import HttpTransport, UrllibTransport
from jobfindsme.contracts import DiscoverySource, DiscoverySourceKind
from jobfindsme.importing.parsers import parse_csv, parse_json
from jobfindsme.importing.service import ImportSummary, JobImportService


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
            DiscoverySourceKind.LAGOU_CDP,
            DiscoverySourceKind.WUYOU_CDP,
        }:
            from jobfindsme.connectors.china_platforms import (
                LagouConnector,
                LiepinConnector,
                WuyouConnector,
                ZhilianConnector,
            )

            connector_cls = {
                DiscoverySourceKind.LIEPIN_CDP: LiepinConnector,
                DiscoverySourceKind.ZHILIAN_CDP: ZhilianConnector,
                DiscoverySourceKind.LAGOU_CDP: LagouConnector,
                DiscoverySourceKind.WUYOU_CDP: WuyouConnector,
            }[source.kind]
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
