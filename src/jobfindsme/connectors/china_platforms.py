"""猎聘 / 智联招聘 / 拉勾 CDP connectors.

Shares the same Chrome CDP session used by BossZhipinConnector.
User logs into all platforms once via `jobfindsme boss-setup`;
subsequent searches call each platform's page from the browser context
and extract structured job records from the rendered DOM.

Based on career-ops-cn (DavePenn, MIT) — Puppeteer + DOM extraction.
"""

from __future__ import annotations

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


def _cdp_fetch(
    search_url: str,
    extract_js: str,
    *,
    port: int = DEFAULT_CDP_PORT,
    session_factory: Callable[[int], CdpSession] = _CDPSession,
    wait_ms: int = 4000,
) -> list[dict[str, Any]]:
    """Navigate to a search page via CDP, inject JS, return extracted jobs."""
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
                    "Object.defineProperty(document,'visibilityState',{get:()=>'visible'});"
                )
            },
            sid,
        )
        cdp.send("Page.navigate", {"url": search_url}, sid)
        time.sleep(wait_ms / 1000)

        raw = cdp.eval_js(extract_js, sid)
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return []
        return []
    finally:
        if target_id is not None:
            with suppress(Exception):
                cdp.send("Target.closeTarget", {"targetId": target_id})
        cdp.close()


# ── 猎聘 ─────────────────────────────────────────────────────────────────────

LIEPIN_CITY_CODES = {"北京": "010", "上海": "020", "深圳": "050090", "杭州": "080020",
                     "广州": "050020", "成都": "280020", "武汉": "170020", "南京": "060020"}  # noqa: E501

_LIEPIN_EXTRACT_JS = """
(function(){
    var results = [];
    var cards = document.querySelectorAll('[class*="job-card-pc-container"]');
    cards.forEach(function(card) {
        var text = (card.textContent || '').replace(/\\s+/g, ' ').trim();
        var linkEl = card.querySelector('a[data-nick="job-detail-job-info"]');
        var url = linkEl ? linkEl.href : '';
        var titleMatch = text.match(/^(.+?)(?:【|$)/);
        var salaryMatch = text.match(/(\\d+[-~·]\\d+[kK万](?:[·.]\\d+薪)?)/);
        var cityMatch = text.match(/【([^】]+)】/);
        var companyMatch = text.match(/(?:统招本科|大专|硕士|博士|学历不限|经验不限)\\s*(.+?)(?:互联网|金融|教育|医疗|房地产|专业技术|机械|制造|消费品|汽车|电子|通信|游戏|文化|零售|物流|能源|农业|政府||[A-Z]轮|上市|融资|天使)/);
        if (titleMatch && titleMatch[1].trim()) {
            results.push({
                title: titleMatch[1].trim(),
                company: companyMatch ? companyMatch[1].trim() : '',
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
        url = (
            "https://www.liepin.com/zhaopin/?"
            f"key={self.keyword}&dqs={dqs}"
        )
        items = _cdp_fetch(url, _LIEPIN_EXTRACT_JS, port=self.cdp_port)
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=item.get("url", "") or item.get("title", ""),
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


# ── 智联招聘 ─────────────────────────────────────────────────────────────────

_ZHILIAN_EXTRACT_JS = """
(function(){
    var results = [];
    var cards = document.querySelectorAll('[class*="joblist-box"], [class*="positionlist"], .joblist-box__item, [class*="job-card"]');
    if (!cards.length) {
        // Fallback: search for any div containing job title patterns
        var allDivs = document.querySelectorAll('div');
        allDivs.forEach(function(div) {
            var text = div.textContent.trim();
            if (text.length > 20 && text.length < 500 && /工程师|经理|产品|研发|开发|设计|算法/.test(text)) {
                var link = div.querySelector('a');
                results.push({
                    title: text.split(/\\s+/)[0] || text.slice(0,40),
                    company: '',
                    salary: (text.match(/(\\d+[-~]\\d+[Kk])/) || [''])[0],
                    city: (text.match(/(北京|上海|深圳|广州|杭州|成都|武汉|南京|苏州|西安|重庆)/) || [''])[0],
                    url: link ? link.href : ''
                });
            }
        });
    } else {
        cards.forEach(function(card) {
            var text = (card.textContent || '').replace(/\\s+/g, ' ').trim();
            var link = card.querySelector('a');
            results.push({
                title: text.split(/\\s+/)[0] || text.slice(0, 50),
                company: (text.match(/(.{2,20}?(?:有限公司|科技|集团|网络|软件|信息|数据|云计算|人工智能|机器人))/) || [''])[0],
                salary: (text.match(/(\\d+[-~]\\d+[Kk])/) || [''])[0],
                city: (text.match(/(北京|上海|深圳|广州|杭州|成都|武汉|南京|苏州|西安|重庆)/) || [''])[0],
                url: link ? link.href : ''
            });
        });
    }
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
        items = _cdp_fetch(
            url, _ZHILIAN_EXTRACT_JS, port=self.cdp_port, wait_ms=6000
        )
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=item.get("url", "") or item.get("title", ""),
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


# ── 拉勾 ─────────────────────────────────────────────────────────────────────

_LAGOU_EXTRACT_JS = """
(function(){
    var results = [];
    var items = document.querySelectorAll('[class*="job-card"], [class*="position"], .job-item, li');
    items.forEach(function(item) {
        var text = (item.textContent || '').replace(/\\s+/g, ' ').trim();
        var link = item.querySelector('a');
        var titleEl = item.querySelector('[class*="title"], [class*="name"], h3, h2');
        var title = titleEl ? titleEl.textContent.trim() : text.slice(0, 40);
        if (title && title.length > 2 && title.length < 80) {
            results.push({
                title: title,
                company: (text.match(/(.{2,20}?(?:科技|有限公司|集团|网络|软件))/) || [''])[0],
                salary: (text.match(/(\\d+[-~]\\d+[kK])/) || [''])[0],
                city: (text.match(/(北京|上海|深圳|广州|杭州|成都|武汉|南京)/) || [''])[0],
                url: link ? link.href : ''
            });
        }
    });
    return JSON.stringify(results.slice(0, 15));
})()
"""  # noqa: E501


class LagouConnector:
    """Discover jobs from 拉勾 via Chrome CDP + DOM extraction."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "拉勾",
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port

    def fetch(self) -> list[RawJobRecord]:
        city_code = {"上海": "上海", "北京": "北京", "深圳": "深圳",
                      "杭州": "杭州", "广州": "广州"}.get(self.city, "")
        city_param = f"&city={city_code}" if city_code else ""
        url = (
            f"https://www.lagou.com/wn/jobs?kd={self.keyword}{city_param}"
        )
        items = _cdp_fetch(
            url, _LAGOU_EXTRACT_JS, port=self.cdp_port, wait_ms=6000
        )
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=item.get("url", "") or item.get("title", ""),
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


# ── 前程无忧 (51job) ─────────────────────────────────────────────────────────

_WUYOU_EXTRACT_JS = """  # noqa: E501
(function(){
    var results = [];
    var items = document.querySelectorAll('.joblist-item');
    items.forEach(function(item) {
        var titleEl = item.querySelector('.jname');
        var companyEl = item.querySelector('.cname');
        var salaryEl = item.querySelector('[class*="sal"]');
        var locationEl = item.querySelector('[class*="location"], [class*="area"], [class*="city"]');
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
"""

_WUYOU_CITY_CODES = {
    "北京": "010000", "上海": "020000", "深圳": "040000",
    "广州": "030200", "杭州": "080200", "成都": "090200",
    "武汉": "180200", "南京": "070200", "苏州": "070300",
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
        items = _cdp_fetch(
            url, _WUYOU_EXTRACT_JS, port=self.cdp_port, wait_ms=6000
        )
        return [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name=self.source_name,
                source_url=url,
                external_id=item.get("url", "") or item.get("title", ""),
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
