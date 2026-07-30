"""Passive Network-interception connectors for 前程无忧 and 智联招聘.

Instead of fragile DOM regex extraction, these connectors navigate to the
search page, let the SPA make its own API calls, and intercept the JSON
responses via CDP Network monitoring.  The page's own JavaScript handles
all signing, cookies, and CORS — we just read the response body.

The fixed _CDPSession (read/write separation with background reader thread)
makes this possible: CDP events (Network.responseReceived etc.) are buffered
in a queue that we drain, while send() waits on its own future.
"""

from __future__ import annotations

import json
import time
from contextlib import suppress
from typing import Any

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.boss_zhipin import (
    DEFAULT_CDP_PORT,
    _CDPSession,
)
from jobfindsme.contracts import SourceKind


class InterceptionFailedError(RuntimeError):
    """Passive CDP interception failed at transport level (timeout, no Chrome,
    page structure changed).  Distinct from a successful-but-empty API
    response: discovery uses this to decide whether to fall back to DOM."""


def _intercept_api_response(
    search_url: str,
    api_url_patterns: tuple[str, ...],
    *,
    port: int = DEFAULT_CDP_PORT,
    wait_ms: int = 8000,
) -> dict[str, Any] | None:
    """Navigate to *search_url* and intercept the SPA's API call.

    The SPA loads, computes its own signatures, and calls its backend
    API.  We capture the response via CDP Network monitoring without
    injecting any code or computing any signatures ourselves.

    Returns the parsed JSON response body, or None on failure.
    """
    cdp = _CDPSession(port)
    target_id: str | None = None
    sid: str | None = None

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

        cdp.send("Page.navigate", {"url": search_url}, sid=sid)

        captured_request_id: str | None = None
        deadline = time.monotonic() + max(wait_ms / 1000, 10)

        while time.monotonic() < deadline:
            for event in cdp.drain_events():
                method = event.get("method", "")
                params = event.get("params", {})

                if method == "Network.responseReceived":
                    resp = params.get("response", {})
                    url = resp.get("url", "")
                    if resp.get("status") == 200 and any(
                        p in url for p in api_url_patterns
                    ):
                        captured_request_id = params.get("requestId")

                if (
                    method == "Network.loadingFinished"
                    and params.get("requestId") == captured_request_id
                    and captured_request_id
                ):
                    try:
                        result = cdp.send(
                            "Network.getResponseBody",
                            {"requestId": captured_request_id},
                            sid=sid,
                        )
                        body = result.get("result", {}).get("body", "")
                        if body:
                            return json.loads(body)
                    except Exception:
                        pass
                    captured_request_id = None
            time.sleep(0.15)

        return None
    except Exception:
        return None
    finally:
        if target_id is not None:
            with suppress(Exception):
                cdp.send("Target.closeTarget", {"targetId": target_id})
        cdp.close()


# ── 前程无忧 (51job) ─────────────────────────────────────────────────────────

_WUYOU_CITY: dict[str, str] = {
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
    """Discover jobs from 前程无忧 via passive CDP Network interception."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "前程无忧",
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port

    def fetch(self) -> list[RawJobRecord]:
        from urllib.parse import quote

        city_code = _WUYOU_CITY.get(self.city, "000000")
        # NOTE: the SPA reads `jobArea`, not `location`.  Passing `location`
        # silently ignores the filter and the page falls back to IP
        # geolocation (e.g. 020000/上海 never applied → 深圳 results).
        search_url = (
            "https://we.51job.com/pc/search"
            f"?keyword={quote(self.keyword)}&jobArea={city_code}"
        )

        data = _intercept_api_response(
            search_url,
            ("search-pc",),
            port=self.cdp_port,
        )
        if data is None:
            raise InterceptionFailedError(
                "51job search-pc interception failed (transport)"
            )
        if not data:
            return []

        body = data.get("resultbody", data)
        if not isinstance(body, dict):
            return []
        # search-pc returns jobs nested as resultbody.job.items (list)
        jobs_raw = body.get("job", body.get("data", {}))
        if isinstance(jobs_raw, dict):
            jobs_raw = jobs_raw.get("items", jobs_raw)
        if isinstance(jobs_raw, dict):
            jobs: list[dict] = list(jobs_raw.values())
        elif isinstance(jobs_raw, list):
            jobs = jobs_raw
        else:
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
                    "company": str(
                        item.get("fullCompanyName", item.get("companyName", ""))
                    ),
                    "description": str(
                        item.get("jobDescribe", item.get("description", ""))
                    ),
                    "location": str(
                        item.get("jobAreaString", item.get("location", ""))
                    ),
                    "salary": str(
                        item.get(
                            "provideSalaryString",
                            item.get("salary", ""),
                        )
                    ),
                    "url": str(item.get("jobHref", item.get("url", ""))),
                    "apply_url": str(item.get("jobHref", item.get("url", ""))),
                },
            )
            for item in jobs
            if isinstance(item, dict) and (item.get("jobName") or item.get("title"))
        ]


# ── 智联招聘 ─────────────────────────────────────────────────────────────────

# 智联搜索页 SPA 读取 `jl`（cityId），不是中文城市名。
_ZHILIAN_CITY: dict[str, str] = {
    "北京": "530",
    "上海": "538",
    "广州": "763",
    "深圳": "765",
    "杭州": "653",
    "成都": "801",
    "武汉": "736",
    "南京": "635",
    "苏州": "639",
}


class ZhilianHttpConnector:
    """Discover jobs from 智联招聘 via passive CDP Network interception."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "智联招聘",
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port

    def fetch(self) -> list[RawJobRecord]:
        from urllib.parse import quote

        city_id = _ZHILIAN_CITY.get(self.city, "")
        city_param = f"&jl={city_id}" if city_id else ""
        search_url = (
            f"https://sou.zhaopin.com/?kw={quote(self.keyword)}&p=1{city_param}"
        )

        # 智联 SPA 实际调用 fe-api.zhaopin.com/c/i/sou（已验证 200 匿名可达）；
        # 旧 pattern "portal/job/search" 返回 404，永远不会命中。
        data = _intercept_api_response(
            search_url,
            ("/c/i/sou",),
            port=self.cdp_port,
        )
        if data is None:
            raise InterceptionFailedError(
                "zhilian fe-api /c/i/sou interception failed (transport)"
            )
        if not data:
            return []

        jobs_raw = data.get("data", data)
        if isinstance(jobs_raw, dict):
            jobs_raw = jobs_raw.get("results", jobs_raw.get("list", []))
        if isinstance(jobs_raw, dict):
            jobs: list[dict] = list(jobs_raw.values())
        elif isinstance(jobs_raw, list):
            jobs = jobs_raw
        else:
            return []

        def _city_of(item: dict) -> str:
            work_city = item.get("workCity")
            if isinstance(work_city, dict):
                return str(work_city.get("name", ""))
            return str(work_city or item.get("cityName", item.get("city", "")))

        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=search_url,
                external_id=str(
                    item.get(
                        "number",
                        item.get("positionId", item.get("id", item.get("jobName", ""))),
                    )
                ),
                payload={
                    "title": str(item.get("jobName", item.get("title", ""))),
                    "company": str(item.get("companyName", item.get("company", ""))),
                    "description": str(
                        item.get(
                            "jobSummary",
                            item.get("jobDescription", item.get("description", "")),
                        )
                    ),
                    "location": _city_of(item),
                    "salary": str(
                        item.get(
                            "salary60",
                            item.get("salaryDetail", item.get("salary", "")),
                        )
                    ),
                    "url": str(item.get("positionURL", item.get("url", ""))),
                    "apply_url": str(item.get("positionURL", item.get("url", ""))),
                },
            )
            for item in jobs
            if isinstance(item, dict) and (item.get("jobName") or item.get("title"))
        ]
