from __future__ import annotations

import json

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.http import HttpTransport, validate_public_http_url
from jobfindsme.contracts import SourceKind


class GreenhouseConnector:
    """Read Greenhouse's public Job Board API through an injected transport."""

    def __init__(
        self,
        board_token: str,
        *,
        transport: HttpTransport,
        policy: ConnectorPolicy,
        source_name: str | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        if not board_token.replace("-", "").isalnum():
            raise ValueError("invalid Greenhouse board token")
        self.board_token = board_token
        self.transport = transport
        self.source_name = source_name or f"greenhouse:{board_token}"

    def fetch(self) -> list[RawJobRecord]:
        url = (
            "https://boards-api.greenhouse.io/v1/boards/"
            f"{self.board_token}/jobs?content=true"
        )
        validate_public_http_url(url)
        document = json.loads(self.transport.get(url))
        return [
            RawJobRecord(
                source_kind=SourceKind.ATS,
                source_name=self.source_name,
                source_url=url,
                external_id=str(item["id"]),
                payload=item,
            )
            for item in document.get("jobs", [])
        ]
