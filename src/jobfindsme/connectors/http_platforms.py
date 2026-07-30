"""HTTP API connectors for 前程无忧 (51job) and 智联招聘 via in-page fetch.

Rather than fragile DOM regex extraction, these connectors navigate to the
search page, then evaluate JavaScript that calls fetch() against the SPA's
own backend API from within the authenticated page context. The page's JS
environment handles all signing/cookies automatically.

This is a transitional step toward pure-HTTP connectors; the data quality
is already much better than DOM extraction — structured JSON with all fields.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.boss_zhipin import (
    DEFAULT_CDP_PORT,
    CdpSession,
    _CDPSession,
)
from jobfindsme.contracts import SourceKind


def _fetch_json_from_page(
    search_url: str,
    api_url_pattern: str,
    *,
    port: int = DEFAULT_CDP_PORT,
    session_factory: Callable[[int], CdpSession] = _CDPSession,
    wait_ms: int = 6000,
) -> dict[str, Any] | None:
    """Navigate to search_url, then fetch(api_url_pattern) from page context.

    The page's own JS computes any required signatures/cookies. We just
    eval a fetch() call and return the parsed JSON response.
    """
    cdp = session_factory(port)
    target_id: str | None = None
    try:
        target = cdp.send(
            "Target.createTarget",
            {"url": "about:blank", "background": True},
        )
        target_id = target["result"]["targetId"]
        attached = cdp.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        sid = attached["result"]["sessionId"]
        cdp.send("Network.enable", sid=sid)
        cdp.send("Page.enable", sid=sid)
        cdp.send("Runtime.enable", sid=sid)
        cdp.send("Page.navigate", {"url": search_url}, sid=sid)

        # Wait for SPA to render (same dwell logic as _cdp_fetch)
        deadline = time.monotonic() + max(wait_ms / 1000, 10)
        body_met_at: float | None = None
        while time.monotonic() < deadline:
            state = cdp.eval_js("document.readyState", sid)
            if state in {"interactive", "complete"}:
                body_len = cdp.eval_js("document.body.innerText.length", sid)
                if isinstance(body_len, (int, float)) and body_len > 200:
                    if body_met_at is None:
                        body_met_at = time.monotonic()
                    if time.monotonic() - body_met_at >= 2.0:
                        break
            time.sleep(0.3)

        # Call fetch() from page context — the page's JS handles signing
        js = """
(async function(){
    try {
        var resp = await fetch('%s', {credentials: 'include'});
        if (!resp.ok) return JSON.stringify({error: resp.status});
        var text = await resp.text();
        return text;
    } catch(e) { return JSON.stringify({error: e.message}); }
})()
""".replace("%s", api_url_pattern)
        raw = cdp.eval_js(js, sid)
        if isinstance(raw, str) and raw:
            return json.loads(raw)
        return None
    except Exception:
        return None
    finally:
        if target_id is not None:
            with suppress(Exception):
                cdp.send("Target.closeTarget", {"targetId": target_id})
        cdp.close()


# ── 前程无忧 (51job) ─────────────────────────────────────────────────────────

_WUYOU_CITY = {
    "北京": "010000",
    "上海": "020000",
    "深圳": "040000",
    "广州": "030200",
    "杭州": "080200",
    "成都": "090200",
    "武汉": "180200",
    "南京": "070200",
    "苏州": "070300",
}


class WuyouHttpConnector:
    """Discover jobs from 前程无忧 via in-page fetch to cupid API."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "前程无忧",
        cdp_port: int = DEFAULT_CDP_PORT,
        session_factory: Callable[[int], CdpSession] = _CDPSession,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port
        self.session_factory = session_factory

    def fetch(self) -> list[RawJobRecord]:
        from urllib.parse import quote

        city_code = _WUYOU_CITY.get(self.city, "000000")
        search_url = (
            "https://we.51job.com/pc/search"
            f"?keyword={quote(self.keyword)}&location={city_code}"
        )
        ts = int(time.time() * 1000)
        api_url = (
            "https://cupid.51job.com/open/noauth/jobs/seo-job-list/normal"
            f"?api_key=51job&timestamp={ts}"
            f"&keyword={quote(self.keyword)}"
            f"&location={city_code}&pageNum=1&pageSize=40"
        )
        data = _fetch_json_from_page(
            search_url,
            api_url,
            port=self.cdp_port,
            session_factory=self.session_factory,
        )
        if not data:
            return []

        jobs = data.get("resultbody", data)
        if isinstance(jobs, dict):
            jobs = jobs.get("joblist", jobs.get("list", jobs.get("data", [])))
        if not isinstance(jobs, list):
            return []

        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=search_url,
                external_id=str(
                    item.get("jobId", item.get("id", item.get("jobName", "")))
                ),
                payload={
                    "title": str(item.get("jobName", item.get("title", ""))),
                    "company": str(item.get("companyName", item.get("company", ""))),
                    "description": str(
                        item.get("jobDescription", item.get("description", ""))
                    ),
                    "location": str(item.get("workArea", item.get("location", ""))),
                    "salary": str(item.get("salaryDesc", item.get("salary", ""))),
                    "url": str(item.get("jobUrl", item.get("url", ""))),
                    "apply_url": str(item.get("jobUrl", item.get("url", ""))),
                },
            )
            for item in jobs
            if isinstance(item, dict) and item.get("jobName") or item.get("title")
        ]


# ── 智联招聘 ─────────────────────────────────────────────────────────────────


class ZhilianHttpConnector:
    """Discover jobs from 智联招聘 via in-page fetch."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "智联招聘",
        cdp_port: int = DEFAULT_CDP_PORT,
        session_factory: Callable[[int], CdpSession] = _CDPSession,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port
        self.session_factory = session_factory

    def fetch(self) -> list[RawJobRecord]:
        from urllib.parse import quote

        city_param = f"&city={quote(self.city)}" if self.city else ""
        search_url = (
            f"https://sou.zhaopin.com/?kw={quote(self.keyword)}&p=1{city_param}"
        )
        # The SPA calls this portal API; construct the URL pattern
        api_url = (
            "https://fe-api.zhaopin.com/c/i/portal/job/search"
            f"?kw={quote(self.keyword)}&p=1{city_param}"
            "&pageSize=40"
        )
        data = _fetch_json_from_page(
            search_url,
            api_url,
            port=self.cdp_port,
            session_factory=self.session_factory,
        )
        if not data:
            return []

        jobs = data.get("data", data)
        if isinstance(jobs, dict):
            jobs = jobs.get("list", jobs.get("results", jobs.get("data", [])))

        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=search_url,
                external_id=str(
                    item.get("positionId", item.get("id", item.get("title", "")))
                ),
                payload={
                    "title": str(item.get("jobName", item.get("title", ""))),
                    "company": str(item.get("companyName", item.get("company", ""))),
                    "description": str(
                        item.get("jobDescription", item.get("description", ""))
                    ),
                    "location": str(item.get("city", item.get("location", ""))),
                    "salary": str(item.get("salaryDetail", item.get("salary", ""))),
                    "url": str(item.get("positionURL", item.get("url", ""))),
                    "apply_url": str(item.get("positionURL", item.get("url", ""))),
                },
            )
            for item in jobs
            if isinstance(item, dict) and item.get("jobName") or item.get("title")
        ]
