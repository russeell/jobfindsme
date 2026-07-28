from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.http import HttpTransport, validate_public_http_url
from jobfindsme.contracts import SourceKind

INITIAL_DATA = re.compile(
    rb"window\.__INITIAL_DATA__\s*=(.*?);\s*window\.prefix=",
    re.DOTALL,
)

_JS_UNDEFINED = re.compile(r":\s*undefined\b")


def _sanitize_js_json(raw: str) -> str:
    """Replace JavaScript literals that are invalid in JSON."""
    return _JS_UNDEFINED.sub(":null", raw)


class BaiduCareerConnector:
    """Read the first server-rendered page of Baidu's public social job search."""

    def __init__(
        self,
        query: str,
        *,
        transport: HttpTransport,
        policy: ConnectorPolicy,
        source_name: str = "百度招聘",
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.query = query.strip()
        if not self.query or len(self.query) > 100:
            raise ValueError("invalid Baidu career query")
        self.transport = transport
        self.source_name = source_name

    def fetch(self) -> list[RawJobRecord]:
        url = (
            f"https://talent.baidu.com/jobs/social-list?search={quote_plus(self.query)}"
        )
        validate_public_http_url(url, require_https=True)
        document = self.transport.get(url)
        match = INITIAL_DATA.search(document)
        if match is None:
            raise ValueError("Baidu career page did not contain initial job data")
        raw = match.group(1).decode("utf-8", errors="replace")
        initial = json.loads(_sanitize_js_json(raw))
        jobs = initial.get("listData", {}).get("listDetailData", [])
        return [
            self._record(item, source_url=url)
            for item in jobs
            if isinstance(item, dict) and item.get("jobId") and item.get("name")
        ]

    def _record(self, item: dict[str, Any], *, source_url: str) -> RawJobRecord:
        job_id = str(item["jobId"])
        detail_url = f"https://talent.baidu.com/jobs/detail/SOCIAL/{job_id}"
        description = "\n".join(
            part
            for part in (
                str(item.get("workContent") or ""),
                str(item.get("serviceCondition") or ""),
            )
            if part
        )
        return RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name=self.source_name,
            source_url=source_url,
            external_id=job_id,
            payload={
                "title": item["name"],
                "company": "百度",
                "description": description,
                "location": item.get("workPlace") or "",
                "published_at": item.get("updateDate") or item.get("publishDate"),
                "url": detail_url,
                "apply_url": detail_url,
                "experience": item.get("workYears") or "",
            },
        )
