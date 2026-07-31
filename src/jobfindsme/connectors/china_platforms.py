"""猎聘、智联招聘和前程无忧 CDP connectors.

Shares the same Chrome CDP session used by BossZhipinConnector.
User logs into all platforms once via `jobfindsme boss-setup`;
subsequent searches call each platform's page from the browser context
and extract structured job records from the rendered DOM.

Based on career-ops-cn (DavePenn, MIT) — Puppeteer + DOM extraction.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.boss_zhipin import DEFAULT_CDP_PORT, _CDPSession
from jobfindsme.contracts import SourceKind


class CdpSession(Protocol):
    def send(
        self, method: str, params: dict | None = None, sid: str | None = None
    ) -> dict: ...
    def eval_js(self, js: str, sid: str) -> Any: ...
    def close(self) -> None: ...


# ── Shared CDP helpers ──────────────────────────────────────────────────────


class CdpFetchError(Exception):
    """Raised when CDP navigation or extraction fails after retries."""


class CdpBlockedError(CdpFetchError):
    """Raised when a platform returns a login, CAPTCHA, or risk-control page."""


def _wait_for_selectors(
    cdp: CdpSession,
    sid: str,
    selectors: list[str],
    timeout_ms: int = 8000,
) -> None:
    """Poll until at least one selector matches or timeout."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for sel in selectors:
            count = cdp.eval_js(
                f"document.querySelectorAll({json.dumps(sel)}).length", sid
            )
            if isinstance(count, (int, float)) and count > 0:
                return
        time.sleep(0.3)
    # Timeout — continue anyway, extraction JS may still find content


def _cdp_fetch(
    search_url: str,
    extract_js: str,
    *,
    port: int = DEFAULT_CDP_PORT,
    session_factory: Callable[[int], CdpSession] = _CDPSession,
    wait_ms: int = 2000,
    retries: int = 2,
) -> list[dict[str, Any]]:
    """Navigate to a search page via CDP, inject JS, return extracted jobs.

    Raises CdpFetchError on persistent failure so callers can distinguish
    "no jobs found" from "extraction broken".
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
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
            cdp.send("Page.enable", sid=sid)
            cdp.send("Runtime.enable", sid=sid)
            cdp.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": (
                        "Object.defineProperty(document,'hidden',{get:()=>false});"
                        "Object.defineProperty(document,'visibilityState',"
                        "{get:()=>'visible'});"
                    )
                },
                sid,
            )
            cdp.send("Page.navigate", {"url": search_url}, sid)

            # Poll for readyState + stable content (SPA pages populate
            # job cards asynchronously after the initial shell renders).
            deadline = time.monotonic() + max(wait_ms / 1000, 8)
            body_met_at: float | None = None
            while time.monotonic() < deadline:
                state = cdp.eval_js("document.readyState", sid)
                if state in {"interactive", "complete"}:
                    body_len = cdp.eval_js("document.body.innerText.length", sid)
                    if isinstance(body_len, (int, float)) and body_len > 200:
                        if body_met_at is None:
                            body_met_at = time.monotonic()
                        # Wait 2s after body threshold for SPA rendering
                        if time.monotonic() - body_met_at >= 2.0:
                            break
                time.sleep(0.3)

            raw = cdp.eval_js(extract_js, sid)
            if isinstance(raw, str):
                items = json.loads(raw)
                if items:
                    return items
                blocked_reason = _blocked_page_reason(cdp, sid)
                if blocked_reason:
                    raise CdpBlockedError(blocked_reason)
                return []
            return []
        except CdpBlockedError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
        finally:
            if target_id is not None:
                with suppress(Exception):
                    cdp.send("Target.closeTarget", {"targetId": target_id})
            cdp.close()
    raise CdpFetchError(
        f"CDP extraction failed after {retries + 1} attempts: {last_error}"
    ) from last_error


def _sanitize_external_id(url: str, fallback: str = "") -> str:
    """Return a stable bounded ID without truncation collisions."""
    from urllib.parse import urlparse

    if not url:
        return fallback
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="").geturl()
    if parsed.path not in {"", "/"} and len(clean) <= 256:
        return clean
    return f"url_{hashlib.sha256(url.encode()).hexdigest()}"


def _detail_extract_js(platform: str) -> str:
    selectors = {
        "liepin": (
            '[class*="job-intro"]',
            '[class*="job-detail"]',
            '[class*="job-require"]',
        ),
        "zhilian": (
            '[class*="job-detail"]',
            '[class*="describ"]',
            '[class*="position-detail"]',
        ),
    }.get(platform, ())
    selector_json = json.dumps(selectors, ensure_ascii=False)
    return f"""
(function(){{
    var selectors = {selector_json};
    var candidates = [];
    selectors.forEach(function(selector) {{
        document.querySelectorAll(selector).forEach(function(element) {{
            candidates.push(element);
        }});
    }});
    if (!candidates.length) {{
        candidates = Array.from(
            document.querySelectorAll('div, section, article, p, pre')
        );
    }}
    var best = '';
    candidates.forEach(function(element) {{
        var text = (element.textContent || '').replace(/\\s+/g, ' ').trim();
        var jd = /职责|要求|任职|岗位描述|职位描述|qualifications|requirements/i;
        if (text.length > 100 && text.length < 12000
            && jd.test(text) && text.length > best.length) {{
            best = text;
        }}
    }});
    return best;
}})()
"""


def _cdp_fetch_detail(
    detail_url: str,
    *,
    platform: str,
    port: int = DEFAULT_CDP_PORT,
    session_factory: Callable[[int], CdpSession] = _CDPSession,
    timeout_seconds: float = 5.0,
    dwell_seconds: float = 0.5,
) -> str:
    """Extract one detail page while always closing its target and session."""
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
        cdp.send("Page.enable", sid=sid)
        cdp.send("Runtime.enable", sid=sid)
        cdp.send("Page.navigate", {"url": detail_url}, sid=sid)

        deadline = time.monotonic() + timeout_seconds
        ready_at: float | None = None
        while time.monotonic() < deadline:
            state = cdp.eval_js("document.readyState", sid)
            if state in {"interactive", "complete"}:
                body_len = cdp.eval_js("document.body.innerText.length", sid)
                if isinstance(body_len, (int, float)) and body_len > 200:
                    ready_at = ready_at or time.monotonic()
                    if time.monotonic() - ready_at >= dwell_seconds:
                        break
            time.sleep(0.2)

        raw = cdp.eval_js(_detail_extract_js(platform), sid)
        return raw.strip() if isinstance(raw, str) else ""
    except Exception:
        return ""
    finally:
        if target_id is not None:
            with suppress(Exception):
                cdp.send("Target.closeTarget", {"targetId": target_id})
        cdp.close()


def enrich_job_descriptions(
    records: list[RawJobRecord],
    *,
    platform: str,
    limit: int = 3,
    budget_seconds: float = 12.0,
    port: int = DEFAULT_CDP_PORT,
    detail_fetcher: Callable[..., str] = _cdp_fetch_detail,
) -> list[RawJobRecord]:
    """Best-effort bounded enrichment for list-card records."""
    enriched = list(records)
    started = time.monotonic()
    attempts = 0
    for index, record in enumerate(records):
        if attempts >= limit or time.monotonic() - started >= budget_seconds:
            break
        payload = dict(record.payload)
        url = str(payload.get("url") or payload.get("apply_url") or "")
        if not url or payload.get("description"):
            continue
        attempts += 1
        remaining = max(0.1, budget_seconds - (time.monotonic() - started))
        description = detail_fetcher(
            url,
            platform=platform,
            port=port,
            timeout_seconds=min(5.0, remaining),
        )
        if not description:
            continue
        enriched[index] = RawJobRecord(
            source_kind=record.source_kind,
            source_name=record.source_name,
            source_url=record.source_url,
            external_id=record.external_id,
            payload={
                **payload,
                "description": description,
                "description_source_url": url,
                "detail_level": "detail_page",
            },
        )
    return enriched


def _blocked_page_reason(cdp: CdpSession, sid: str) -> str | None:
    raw = cdp.eval_js(
        "JSON.stringify({url:location.href,title:document.title,"
        "text:(document.body&&document.body.innerText||'').slice(0,2000)})",
        sid,
    )
    if not isinstance(raw, str):
        return None
    try:
        page = json.loads(raw)
    except json.JSONDecodeError:
        return None
    haystack = " ".join(str(value) for value in page.values()).casefold()
    markers = (
        "滑动验证",
        "安全验证",
        "访问过于频繁",
        "请完成验证",
        "captcha",
        "verify",
    )
    marker = next((value for value in markers if value in haystack), None)
    return f"platform access blocked by {marker}" if marker else None


# ── 猎聘 ─────────────────────────────────────────────────────────────────────

LIEPIN_CITY_CODES = {
    "北京": "010",
    "上海": "020",
    "深圳": "050090",
    "杭州": "080020",
    "广州": "050020",
    "成都": "280020",
    "武汉": "170020",
    "南京": "060020",
}  # noqa: E501

_LIEPIN_EXTRACT_JS = """
(function(){
    var COMPANY_SUFFIX_RE = /有限公司|股份有限公司|有限责任公司|集团有限公司|集团公司|分公司|支行|分行|事务所|中心|工作室|学校|医院|研究院|科技公司|科技|微电子|数据|网络|软件/;
    function _extract_company(card) {
        // Each liepin card has ellipsis-1 spans in fixed order:
        //   [0]=title  [1]=city  [2]=company  [3]=industry+scale
        // Try suffix match first, then fall back to positional.
        var candidates = card.querySelectorAll('[class*="ellipsis-1"]');
        for (var i = 0; i < candidates.length; i++) {
            var text = candidates[i].textContent.trim();
            if (text.length >= 4 && COMPANY_SUFFIX_RE.test(text)) {
                return text;
            }
        }
        // Fallback: the 3rd ellipsis-1 (index 2) is the company slot
        if (candidates.length >= 3) {
            var fallback = candidates[2].textContent.trim();
            if (fallback.length >= 2) return fallback;
        }
        return '';
    }
    var results = [];
    var cards = document.querySelectorAll('[class*="job-card-pc-container"]');
    cards.forEach(function(card) {
        var text = (card.textContent || '').replace(/\\s+/g, ' ').trim();
        var linkEl = card.querySelector('a[data-nick="job-detail-job-info"]');
        var url = linkEl ? linkEl.href : '';
        var titleMatch = text.match(/^(.+?)(?:【|$)/);
        var salaryMatch = text.match(/(\\d+[-~·]\\d+[kK万](?:[·.]\\d+薪)?)/);
        var cityMatch = text.match(/【([^】]+)】/);
        if (titleMatch && titleMatch[1].trim()) {
            results.push({
                title: titleMatch[1].trim(),
                company: _extract_company(card),
                salary: salaryMatch ? salaryMatch[1] : '',
                city: cityMatch ? cityMatch[1] : '',
                url: url
            });
        }
    });
    return JSON.stringify(results);
})()
"""  # noqa: E501


class LiepinConnector:
    """Discover jobs from 猎聘 via Chrome CDP + DOM extraction."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "猎聘",
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port

    def fetch(self) -> list[RawJobRecord]:
        dqs = LIEPIN_CITY_CODES.get(self.city, "010")
        url = f"https://www.liepin.com/zhaopin/?key={self.keyword}&dqs={dqs}"
        items = _cdp_fetch(url, _LIEPIN_EXTRACT_JS, port=self.cdp_port)
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=_sanitize_external_id(
                    item.get("url", ""), item.get("title", "")
                ),
                payload={
                    "title": item.get("title", ""),
                    "company": item.get("company", ""),
                    "description": "",
                    "location": item.get("city", ""),
                    "salary": item.get("salary", ""),
                    "url": item.get("url", ""),
                    "apply_url": item.get("url", ""),
                },
            )
            for item in items
            if item.get("title")
        ]

    def enrich(self, records: list[RawJobRecord], *, limit: int) -> list[RawJobRecord]:
        return enrich_job_descriptions(
            records,
            platform="liepin",
            limit=limit,
            port=self.cdp_port,
        )


# ── 智联招聘 ─────────────────────────────────────────────────────────────────

_ZHILIAN_EXTRACT_JS = """
(function(){
    var results = [];
    // Find job entry cards by their specific class structure
    var cards = document.querySelectorAll('.joblist-box__item, [class*=\"joblist\"] > div');
    var lastCompany = '';
    cards.forEach(function(card) {
        var titleEl = card.querySelector('.jobinfo__name');
        var salaryEl = card.querySelector('.jobinfo__salary');
        var linkEl = card.querySelector('a.jobinfo__name[href*=\"jobdetail\"]');
        var companyEl = card.querySelector('.companyinfo__name');
        var locationEl = card.querySelector('.jobinfo__other-info-item');

        var title = titleEl ? titleEl.textContent.trim() : '';
        // Skip cards that don't look like job entries
        if (!title || title.length < 3 || title.length > 80) return;
        // If this card has company info, remember it for next cards
        if (companyEl) {
            lastCompany = companyEl.textContent.trim();
        }

        results.push({
            title: title,
            company: companyEl ? companyEl.textContent.trim() : lastCompany,
            salary: salaryEl ? salaryEl.textContent.trim() : '',
            city: locationEl ? locationEl.textContent.trim() : '',
            url: linkEl ? linkEl.href : ''
        });
    });
    return JSON.stringify(results.slice(0, 15));
})()
"""  # noqa: E501


class ZhilianConnector:
    """Discover jobs from 智联招聘 via Chrome CDP + DOM extraction."""

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
        city_param = f"&city={self.city}" if self.city else ""
        url = f"https://sou.zhaopin.com/?kw={self.keyword}&p=1{city_param}"
        items = _cdp_fetch(url, _ZHILIAN_EXTRACT_JS, port=self.cdp_port, wait_ms=6000)
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=_sanitize_external_id(
                    item.get("url", ""), item.get("title", "")
                ),
                payload={
                    "title": item.get("title", ""),
                    "company": item.get("company", ""),
                    "description": (
                        item.get("title", "")
                        + "；"
                        + item.get("salary", "")
                        + "；"
                        + item.get("city", "")
                    ),
                    "location": item.get("city", ""),
                    "salary": item.get("salary", ""),
                    "url": item.get("url", ""),
                    "apply_url": item.get("url", ""),
                    "recruitment_track": "social",
                    "employment_type": "full_time",
                },
            )
            for item in items
            if item.get("title")
        ]

    def enrich(self, records: list[RawJobRecord], *, limit: int) -> list[RawJobRecord]:
        return enrich_job_descriptions(
            records,
            platform="zhilian",
            limit=limit,
            port=self.cdp_port,
        )


# ── 前程无忧 (51job) ─────────────────────────────────────────────────────────

_WUYOU_EXTRACT_JS = """
(function(){
    var results = [];
    var items = document.querySelectorAll('.joblist-item');
    items.forEach(function(item) {
        var titleEl = item.querySelector('.jname');
        var companyEl = item.querySelector('.cname');
        var salaryEl = item.querySelector('[class*="sal"]');
        var sel = '[class*="location"], [class*="area"], [class*="city"]';
        var locationEl = item.querySelector(sel);
        var linkEl = item.querySelector('a');
        results.push({
            title: titleEl ? titleEl.textContent.trim() : '',
            company: companyEl ? companyEl.textContent.trim() : '',
            salary: salaryEl ? salaryEl.textContent.trim() : '',
            city: locationEl ? locationEl.textContent.trim() : '',
            url: linkEl ? linkEl.href : ''
        });
    });
    return JSON.stringify(results);
})()
"""  # noqa: E501

_WUYOU_CITY_CODES = {
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


class WuyouConnector:
    """Discover jobs from 前程无忧 (51job) via Chrome CDP + DOM extraction."""

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
        city_code = _WUYOU_CITY_CODES.get(self.city, "000000")
        url = (
            "https://we.51job.com/pc/search"
            f"?keyword={self.keyword}&location={city_code}"
        )
        items = _cdp_fetch(url, _WUYOU_EXTRACT_JS, port=self.cdp_port, wait_ms=6000)
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=_sanitize_external_id(
                    item.get("url", ""), item.get("title", "")
                ),
                payload={
                    "title": item.get("title", ""),
                    "company": item.get("company", ""),
                    "description": "",
                    "location": item.get("city", ""),
                    "salary": item.get("salary", ""),
                    "url": item.get("url", ""),
                    "apply_url": item.get("url", ""),
                },
            )
            for item in items
            if item.get("title")
        ]
