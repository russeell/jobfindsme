from __future__ import annotations

import json

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.http import HttpTransport, validate_public_http_url
from jobfindsme.contracts import SourceKind


class LeverConnector:
    """Read Lever's public Job Board API — 5000+ companies."""

    def __init__(
        self,
        company: str,
        *,
        transport: HttpTransport,
        policy: ConnectorPolicy,
        source_name: str | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        if not company.replace("-", "").isalnum():
            raise ValueError("invalid Lever company identifier")
        self.company = company
        self.transport = transport
        self.source_name = source_name or f"lever:{company}"

    def fetch(self) -> list[RawJobRecord]:
        url = f"https://api.lever.co/v0/postings/{self.company}?mode=json"
        validate_public_http_url(url)
        document = json.loads(self.transport.get(url))
        records: list[RawJobRecord] = []
        for item in document if isinstance(document, list) else document.get("postings", []):
            if not isinstance(item, dict):
                continue
            records.append(
                RawJobRecord(
                    source_kind=SourceKind.ATS,
                    source_name=self.source_name,
                    source_url=url,
                    external_id=str(item.get("id", "")),
                    payload=_normalize_payload(item),
                )
            )
        return records


def _normalize_payload(item: dict) -> dict:
    categories = item.get("categories") or {}
    return {
        "title": item.get("title") or item.get("text", "")[:120],
        "description": item.get("descriptionPlain")
        or item.get("description")
        or item.get("text", ""),
        "locations": _location_list(categories),
        "team": categories.get("team", ""),
        "commitment": categories.get("commitment", ""),
        "created_at": item.get("createdAt"),
        "apply_url": item.get("applyUrl") or item.get("hostedUrl", ""),
        "hosted_url": item.get("hostedUrl", ""),
    }


def _location_list(categories: dict) -> list[str]:
    location = categories.get("location", "")
    if not location:
        return []
    return [location]
