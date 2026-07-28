from __future__ import annotations

from pathlib import Path

from jobfindsme.connectors import (
    AshbyConnector,
    BaiduCareerConnector,
    ConnectorPolicy,
    GreenhouseConnector,
    JsonLdCareerSiteConnector,
    LeverConnector,
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
        if source.kind is DiscoverySourceKind.ASHBY:
            connector = AshbyConnector(
                source.board_name or "",
                transport=self.transport,
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind is DiscoverySourceKind.BAIDU_CAREER:
            connector = BaiduCareerConnector(
                source.query or "",
                transport=self.transport,
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind is DiscoverySourceKind.SPA_PLAYWRIGHT:
            from jobfindsme.connectors.playwright import PlaywrightSpaConnector

            connector = PlaywrightSpaConnector(
                source.site_key or "",
                source.query or "AI",
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind is DiscoverySourceKind.BOSS_CDP:
            from jobfindsme.connectors.boss_zhipin import BossZhipinConnector

            connector = BossZhipinConnector(
                source.query or "AI",
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
        }:
            from jobfindsme.connectors.china_platforms import (
                LagouConnector,
                LiepinConnector,
                ZhilianConnector,
            )

            connector_cls = {
                DiscoverySourceKind.LIEPIN_CDP: LiepinConnector,
                DiscoverySourceKind.ZHILIAN_CDP: ZhilianConnector,
                DiscoverySourceKind.LAGOU_CDP: LagouConnector,
            }[source.kind]
            connector = connector_cls(
                source.query or "AI",
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind is DiscoverySourceKind.GREENHOUSE:
            connector = GreenhouseConnector(
                source.board_token or "",
                transport=self.transport,
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind is DiscoverySourceKind.LEVER:
            connector = LeverConnector(
                source.board_token or "",
                transport=self.transport,
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=True,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)
        if source.kind is DiscoverySourceKind.CAREER_URL:
            connector = JsonLdCareerSiteConnector(
                source.url or "",
                transport=self.transport,
                policy=ConnectorPolicy(
                    public_access=True,
                    robots_allowed=source.robots_allowed,
                ),
                source_name=source.source_name,
            )
            return self.imports.import_connector(workspace_id, connector)

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
