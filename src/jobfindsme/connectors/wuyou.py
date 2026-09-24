"""前程无忧 connector via the SPA search JSON API (pure HTTP).

The 51job SPA calls we.51job.com/api/job/search-pc.  The endpoint sits
behind Aliyun WAF: clean requests return the JSON payload, while suspicious
ones (datacenter IPs, missing browser fingerprint) receive an HTML
challenge.  We detect the challenge explicitly and report it as blocked
instead of pretending the platform had no jobs.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import urlencode

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.boss_zhipin import DEFAULT_CDP_PORT, _CDPSession
from jobfindsme.connectors.pure_http import _UA, _default_session_factory
from jobfindsme.contracts import SourceKind

WUYOU_CITY_CODES = {
    "北京": "010000",
    "上海": "020000",
    "广州": "030000",
    "深圳": "040000",
    "杭州": "080200",
    "南京": "070200",
    "苏州": "070300",
    "成都": "090200",
    "武汉": "180200",
    "西安": "110200",
    "重庆": "130200",
}

_API_URL = "https://we.51job.com/api/job/search-pc"
_TIMEOUT = 12
_WAF_MARKERS = ("aliyun_waf", "_waf_", "<textarea", "acw_sc__v2")


class WuyouError(RuntimeError):
    """Base failure for the 前程无忧 HTTP connector."""


class WuyouBlockedError(WuyouError):
    """The remote returned a security-challenge page instead of jobs."""


class _Response(Protocol):
    status_code: int
    headers: Any
    text: str

    def json(self) -> Any: ...


class _Session(Protocol):
    def get(self, url: str, **kwargs: Any) -> _Response: ...


SessionFactory = Callable[[], _Session]


def _search_params(keyword: str, city: str, *, page_size: int = 30) -> dict[str, str]:
    """Parameters sent by the current 51job web search page."""
    return {
        "api_key": "51job",
        "timestamp": str(int(time.time())),
        "keyword": keyword,
        "searchType": "2",
        "function": "",
        "industry": "",
        "jobArea": WUYOU_CITY_CODES.get(city, "000000"),
        "jobArea2": "",
        "landmark": "",
        "metro": "",
        "salary": "",
        "workYear": "",
        "degree": "",
        "companyType": "",
        "companySize": "",
        "jobType": "",
        "issueDate": "",
        "sortType": "0",
        "pageNum": "1",
        "pageSize": str(page_size),
        "source": "1",
        "scene": "7",
    }


def _search_page_url(keyword: str, city: str) -> str:
    params = {
        "keyword": keyword,
        "searchType": "2",
        "jobArea": WUYOU_CITY_CODES.get(city, "000000"),
    }
    return f"https://we.51job.com/pc/search?{urlencode(params)}"


class WuyouHttpConnector:
    """前程无忧 search via the SPA JSON API (no login, no browser)."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "前程无忧",
        session_factory: SessionFactory | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self._session_factory = session_factory or _default_session_factory

    def fetch(self) -> list[RawJobRecord]:
        params = _search_params(self.keyword, self.city)
        url = f"{_API_URL}?{urlencode(params)}"
        session = self._session_factory()
        try:
            search_page = _search_page_url(self.keyword, self.city)
            session.get(search_page, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
            response = session.get(
                url,
                headers={
                    "User-Agent": _UA,
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": search_page,
                    "Origin": "https://we.51job.com",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                },
                timeout=_TIMEOUT,
            )
        except WuyouError:
            raise
        except Exception as error:
            raise WuyouError(f"51job transport failed: {error}") from error

        lowered = response.text.casefold()
        if "text/html" in str(
            response.headers.get("Content-Type", "")
        ).casefold() or any(marker in lowered for marker in _WAF_MARKERS):
            raise WuyouBlockedError(
                "前程无忧接口被安全校验拦截（返回校验页）；可稍后重试或用浏览器查看"
            )
        try:
            payload = response.json()
        except Exception as error:
            raise WuyouBlockedError(
                f"前程无忧接口返回非 JSON（status {response.status_code}）"
            ) from error
        return _parse_payload(payload, self.source_name)


def _parse_payload(payload: dict[str, Any], source_name: str) -> list[RawJobRecord]:
    if payload.get("status") not in ("1", 1, None):
        raise WuyouBlockedError(
            f"前程无忧接口拒绝：status={payload.get('status')} "
            f"message={payload.get('message')}"
        )
    items = ((payload.get("resultbody") or {}).get("job") or {}).get("items") or []
    return [
        _to_record(item, source_name)
        for item in items
        if isinstance(item, dict) and (item.get("jobId") or item.get("jobid"))
    ]


def _to_record(item: dict[str, Any], source_name: str) -> RawJobRecord:
    def pick(*keys: str) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, "", []):
                return value
        return ""

    title = str(pick("jobName", "job_name"))
    link = str(pick("jobHref", "job_href"))
    if link.startswith("//"):
        link = "https:" + link
    elif link.startswith("/"):
        link = "https://www.51job.com" + link
    job_type_text = str(pick("jobTypeString", "jobtype_text"))
    tags = pick("jobTags", "job_tags") or []
    tag_text = (
        "、".join(str(value) for value in tags) if isinstance(tags, list) else str(tags)
    )
    classification = " ".join((title, job_type_text, tag_text)).casefold()
    recruitment_track = "unknown"
    if any(t in classification for t in ("校招", "校园", "应届")):
        recruitment_track = "campus"
    elif any(t in classification for t in ("社招", "社会招聘")):
        recruitment_track = "social"
    job_type = job_type_text.casefold()
    if item.get("isIntern") is True:
        job_type = "实习"
    employment_type = (
        "internship"
        if "实习" in job_type or "intern" in job_type
        else "part_time"
        if "兼职" in job_type
        else "contract"
        if "合同" in job_type
        else "full_time"
        if any(t in job_type for t in ("正式", "全职", "full-time"))
        else "unknown"
    )
    description = " ".join(
        part
        for part in (
            str(pick("jobDescribe", "job_describe")),
            job_type_text,
            tag_text,
            str(pick("jobwelf", "jobWelf")),
            str(pick("companyTypeString", "companytype_text")),
        )
        if part
    )
    return RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name=source_name,
        source_url=link or _API_URL,
        external_id=str(pick("jobId", "jobid")),
        payload={
            "title": title,
            "company": str(pick("fullCompanyName", "companyName", "company_name")),
            "description": description,
            "location": str(pick("jobAreaString", "workarea_text")),
            "salary": str(pick("provideSalaryString", "providesalary_text")),
            "experience": str(pick("workYearString", "workyear_text")),
            "degree": str(pick("degreeString", "degree_text")),
            "skills": tag_text,
            "url": link,
            "apply_url": link,
            "recruitment_track": recruitment_track,
            "employment_type": employment_type,
            "welfare": str(pick("jobwelf", "jobWelf")),
            "published_at": str(pick("issueDateString", "issue_date", "updatedate")),
        },
    )


_FETCH_JS = """(async () => {
  const url = __API_URL__;
  try {
    const response = await fetch(url, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    const text = await response.text();
    if (text.trimStart().startsWith("<") || text.includes("aliyun_waf")) {
      return JSON.stringify({ error: "waf_blocked", status: response.status });
    }
    return JSON.stringify({ ok: true, text });
  } catch (error) {
    return JSON.stringify({ error: "network_error", message: String(error) });
  }
})()"""


class WuyouCdpConnector:
    """前程无忧 CDP fallback: the real page solves WAF, then we call the API.

    Used only when pure HTTP is challenged.  Requires the user's local
    Dedicated Chrome bridge, same as BOSS直聘.
    """

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "前程无忧",
        cdp_port: int = DEFAULT_CDP_PORT,
        session_factory: Callable[[int], Any] | None = None,
        settle_seconds: float = 2.5,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port
        self.session_factory = session_factory or _CDPSession
        self.settle_seconds = settle_seconds

    def _api_url(self) -> str:
        return f"{_API_URL}?{urlencode(_search_params(self.keyword, self.city))}"

    def _search_url(self) -> str:
        return _search_page_url(self.keyword, self.city)

    def fetch(self) -> list[RawJobRecord]:
        cdp = self.session_factory(self.cdp_port)
        target_id: str | None = None
        try:
            target_id = cdp.send(
                "Target.createTarget",
                {"url": "about:blank", "background": True},
            )["result"]["targetId"]
            sid = cdp.send(
                "Target.attachToTarget",
                {"targetId": target_id, "flatten": True},
            )["result"]["sessionId"]
            cdp.send("Page.enable", sid=sid)
            cdp.send("Runtime.enable", sid=sid)
            cdp.send("Page.navigate", {"url": self._search_url()}, sid)
            self._wait_ready(cdp, sid)
            time.sleep(self.settle_seconds)  # WAF challenge JS + SPA bootstrap
            raw = cdp.eval_js(
                _FETCH_JS.replace("__API_URL__", json.dumps(self._api_url())),
                sid,
            )
            result = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(result, dict) or result.get("error"):
                raise WuyouBlockedError(
                    f"前程无忧页面内请求失败：{result.get('error') or result}"
                )
            return _parse_payload(json.loads(result["text"]), self.source_name)
        finally:
            if target_id is not None:
                with suppress(Exception):
                    cdp.send("Target.closeTarget", {"targetId": target_id})
            cdp.close()

    @staticmethod
    def _wait_ready(cdp: Any, sid: str, timeout_seconds: float = 15) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if cdp.eval_js("document.readyState", sid) in {"interactive", "complete"}:
                return
            time.sleep(0.2)
        raise WuyouError("前程无忧页面加载超时")
