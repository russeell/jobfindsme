"""DeepSeek's first-party published jobs snapshot (not a real-time ATS feed)."""

from __future__ import annotations

import ast
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.company_careers import CompanyCareerError
from jobfindsme.contracts import SourceKind


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in {"p", "li", "div", "br"}:
            self.parts.append("\n")


def parse_snapshot(script: str) -> dict:
    # Parse a literal string only. Never execute the source site's JavaScript.
    match = re.search(r"""JSON\.parse\(('(?:[^'\\]|\\.)*')\)""", script)
    if not match:
        raise CompanyCareerError("DeepSeek published snapshot format changed")
    try:
        data = json.loads(ast.literal_eval(match.group(1)))
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise ValueError("missing jobs")
        if not 0 <= len(data["jobs"]) <= 500 or data.get("total") != len(data["jobs"]):
            raise ValueError("incomplete catalog")
        datetime.fromisoformat(data["crawledAt"].replace("Z", "+00:00"))
    except (ValueError, KeyError, TypeError, SyntaxError) as error:
        raise CompanyCareerError(
            "DeepSeek published snapshot contract changed"
        ) from error
    return data


class DeepSeekCareersConnector:
    home = "https://talent.deepseek.com/"
    _lock = threading.Lock()
    _cache: tuple[float, dict] | None = None
    _retry_after = 0.0

    def __init__(
        self, keyword: str, *, policy: ConnectorPolicy, opener=urllib.request.urlopen
    ):
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip().casefold()
        self.opener = opener

    def _read(self, url: str, limit: int) -> str:
        request = urllib.request.Request(
            url, headers={"User-Agent": "JobFindsMe/desktop-company-careers"}
        )
        with self.opener(request, timeout=8) as response:
            if (
                urllib.parse.urlsplit(response.geturl()).hostname
                != "talent.deepseek.com"
            ):
                raise CompanyCareerError("DeepSeek unexpected redirect")
            content = response.read(limit + 1)
        if len(content) > limit:
            raise CompanyCareerError("DeepSeek response exceeds budget")
        return content.decode("utf-8")

    def snapshot(self) -> dict:
        cls = type(self)
        with (
            cls._lock
        ):  # Single flight, shared across keywords; never cache credentials.
            now = time.monotonic()
            if cls._cache and now - cls._cache[0] < 600:
                return cls._cache[1]
            if now < cls._retry_after:
                raise CompanyCareerError(
                    "DeepSeek request paused after failure; retry later"
                )
            try:
                html = self._read(self.home, 100_000)
                match = re.search(
                    r'src=["\'](/static/main\.[A-Za-z0-9]+\.js)["\']', html
                )
                if not match:
                    raise CompanyCareerError("DeepSeek official script link changed")
                data = parse_snapshot(
                    self._read(urllib.parse.urljoin(self.home, match[1]), 2_000_000)
                )
            except Exception:
                cls._retry_after = time.monotonic() + 300
                raise
            cls._cache = (time.monotonic(), data)
            return data

    def fetch_page(self, page: int = 1):
        if page != 1:
            raise ValueError(
                "DeepSeek publishes one complete catalog; no remote next page"
            )
        data = self.snapshot()
        records = []
        for job in data["jobs"]:
            if not isinstance(job, dict):
                continue
            title, job_id = str(job.get("title", "")).strip(), str(job.get("id", ""))
            if not title or not re.fullmatch(r"[a-f0-9-]{36}", job_id):
                continue
            text = _Text()
            text.feed(str(job.get("descriptionHtml", "")))
            description = "".join(text.parts).strip()
            if (
                self.keyword
                and self.keyword not in (title + " " + description).casefold()
            ):
                continue
            url = str(job.get("detailUrl", ""))
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme, parsed.netloc, parsed.path, parsed.fragment) != (
                "https",
                "app.mokahr.com",
                "/social-recruitment/high-flyer/140576",
                f"/job/{job_id}",
            ):
                continue
            records.append(
                RawJobRecord(
                    source_kind=SourceKind.ATS,
                    source_name="DeepSeek",
                    source_url=self.home,
                    external_id=job_id,
                    payload={
                        "title": title,
                        "company": "DeepSeek",
                        "description": description,
                        "location": "、".join(job.get("locations") or []),
                        "url": url,
                        "apply_url": url,
                        "detail_level": "detail_page"
                        if len(description) >= 80
                        else "structured_source",
                        "description_source_url": self.home,
                        "description_fetched_at": datetime.now(UTC).isoformat(),
                        "source_snapshot_at": data["crawledAt"],
                    },
                )
            )
        return records, None
