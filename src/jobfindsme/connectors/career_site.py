from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.http import HttpTransport, validate_public_http_url
from jobfindsme.contracts import SourceKind


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_json_ld = False
        self.buffers: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("type") == "application/ld+json":
            self.in_json_ld = True
            self.buffers.append([])

    def handle_data(self, data: str) -> None:
        if self.in_json_ld:
            self.buffers[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_json_ld:
            self.in_json_ld = False


def _job_postings(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for item in value:
            records.extend(_job_postings(item))
        return records
    if not isinstance(value, dict):
        return []
    if value.get("@type") == "JobPosting":
        return [value]
    graph = value.get("@graph")
    return _job_postings(graph) if graph else []


class JsonLdCareerSiteConnector:
    """Parse Schema.org JobPosting records from a public career page."""

    def __init__(
        self,
        url: str,
        *,
        transport: HttpTransport,
        policy: ConnectorPolicy,
        source_name: str,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        validate_public_http_url(url)
        self.url = url
        self.transport = transport
        self.source_name = source_name

    def fetch(self) -> list[RawJobRecord]:
        parser = _JsonLdParser()
        parser.feed(self.transport.get(self.url).decode("utf-8", errors="replace"))
        jobs: list[dict[str, Any]] = []
        for buffer in parser.buffers:
            jobs.extend(_job_postings(json.loads("".join(buffer))))
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=self.url,
                external_id=str(
                    item.get("identifier", {}).get("value") or item.get("url") or index
                ),
                payload=item,
            )
            for index, item in enumerate(jobs)
        ]
