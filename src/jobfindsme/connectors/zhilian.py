"""智联招聘 connectors.

The legacy pure-HTTP adapter remains as a browser-free best effort.  The
maintained path navigates the current public search page in the user's local
Chrome and reads the rendered job cards.  This avoids depending on the old
``fe-api /c/i/sou`` response, which now commonly returns a risk-controlled
empty envelope even while the public page contains jobs.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import quote

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.boss_zhipin import DEFAULT_CDP_PORT, _CDPSession
from jobfindsme.connectors.pure_http import _UA, _default_session_factory
from jobfindsme.contracts import SourceKind

ZHILIAN_CITY_CODES = {
    "北京": "530",
    "上海": "538",
    "广州": "654",
    "深圳": "765",
    "杭州": "736",
    "南京": "631",
    "苏州": "639",
    "成都": "801",
    "武汉": "570",
    "西安": "535",
    "重庆": "551",
}

_SEED_URL = "https://sou.zhaopin.com/"
_API_URL = "https://fe-api.zhaopin.com/c/i/sou"
_TIMEOUT = 12


class ZhilianError(RuntimeError):
    """Base failure for the 智联 HTTP connector."""


class ZhilianBlockedError(ZhilianError):
    """The remote challenged or returned an empty risk-controlled envelope."""


class _Response(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class _Session(Protocol):
    cookies: Any

    def get(self, url: str, **kwargs: Any) -> _Response: ...


SessionFactory = Callable[[], _Session]


class ZhilianHttpConnector:
    """智联招聘 search via fe-api JSON (no login, no browser)."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "智联招聘",
        session_factory: SessionFactory | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self._session_factory = session_factory or _default_session_factory

    def fetch(self) -> list[RawJobRecord]:
        city_id = ZHILIAN_CITY_CODES.get(self.city, "")
        seed = f"{_SEED_URL}?jl={city_id}&kw={quote(self.keyword)}"
        api = (
            f"{_API_URL}?pageSize=30&cityId={city_id}&kw={quote(self.keyword)}"
            "&workExperience=-1&education=-1&companyType=-1"
            "&employmentType=-1&jobWelfareTag=-1&kw2=&kt=3"
        )
        session = self._session_factory()
        try:
            session.get(seed, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
            response = session.get(
                api,
                headers={
                    "User-Agent": _UA,
                    "Accept": "application/json, text/plain, */*",
                    "Referer": seed,
                    "Origin": "https://sou.zhaopin.com",
                },
                timeout=_TIMEOUT,
            )
        except ZhilianError:
            raise
        except Exception as error:
            raise ZhilianError(f"zhilian transport failed: {error}") from error

        if (
            "text/html" in response.headers.get("Content-Type", "")
            or "aliyun_waf" in response.text
        ):
            raise ZhilianBlockedError("智联接口被安全校验拦截（返回 HTML 校验页）")
        try:
            payload = response.json()
        except Exception as error:
            raise ZhilianBlockedError(
                f"智联接口返回非 JSON（status {response.status_code}）"
            ) from error
        return _parse_payload(payload, self.source_name)


def _parse_payload(payload: dict[str, Any], source_name: str) -> list[RawJobRecord]:
    """Validate the fe-api envelope and convert results into records."""
    if payload.get("code") not in (200, None) or payload.get("apiCode") not in (
        200,
        None,
    ):
        raise ZhilianBlockedError(
            f"智联接口拒绝：code={payload.get('code')} apiCode={payload.get('apiCode')}"
        )
    results = ((payload.get("data") or {}).get("results")) or []
    num_total = ((payload.get("data") or {}).get("numTotal")) or 0
    if not results and num_total == 0:
        raise ZhilianBlockedError(
            "智联接口返回空结果（可能被风控拦截，请稍后重试或用浏览器查看）"
        )
    return [_to_record(item, source_name) for item in results if isinstance(item, dict)]


def _to_record(item: dict[str, Any], source_name: str) -> RawJobRecord:
    def pick(*keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if isinstance(value, dict):
                value = (
                    value.get("name") or value.get("display") or value.get("__value__")
                )
            if value:
                return str(value)
        return ""

    job_id = str(item.get("jobId") or item.get("number") or "")
    url = str(item.get("positionURL") or "")
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://www.zhaopin.com"):
        url = "https://www.zhaopin.com" + url.removeprefix("http://www.zhaopin.com")
    elif url.startswith("/"):
        url = "https://www.zhaopin.com" + url
    title = pick("jobName", "jobTitle")
    classification = " ".join(
        (title, pick("jobType", "jobTypeText"), pick("workingExp"))
    ).casefold()
    recruitment_track = "unknown"
    if any(t in classification for t in ("校招", "校园", "应届")):
        recruitment_track = "campus"
    elif any(t in classification for t in ("社招", "社会招聘")):
        recruitment_track = "social"
    job_type = pick("jobType", "jobTypeText").casefold()
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
    welfare = item.get("welfare") or []
    skills = item.get("skills") or []
    company_tags = item.get("companyTags") or []
    skill_text = "、".join(str(value) for value in skills) if skills else ""
    description = " ".join(
        part
        for part in (
            title,
            pick("jobType", "jobTypeText"),
            pick("workingExp"),
            pick("eduLevel"),
            pick("companyType"),
            skill_text,
            "、".join(str(value) for value in company_tags),
            "、".join(welfare) if isinstance(welfare, list) else str(welfare),
        )
        if part
    )
    return RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name=source_name,
        source_url=url or _SEED_URL,
        external_id=job_id or json.dumps(item, ensure_ascii=False)[:64],
        payload={
            "title": title,
            "company": pick("companyName"),
            "description": description,
            "location": pick("city"),
            "salary": pick("salary"),
            "experience": pick("workingExp"),
            "degree": pick("eduLevel"),
            "skills": skill_text,
            "url": url,
            "apply_url": url,
            "recruitment_track": recruitment_track,
            "employment_type": employment_type,
            "welfare": "、".join(welfare) if isinstance(welfare, list) else "",
            "updated_at": pick("updateDate"),
        },
    )


_DOM_EXTRACT_JS = r"""(() => {
  const clean = (value) => (value || '').replace(/\s+/g, ' ').trim();
  const text = (root, selector) => clean(root.querySelector(selector)?.textContent);
  const texts = (root, selector) => Array.from(root.querySelectorAll(selector))
    .map((node) => clean(node.textContent)).filter(Boolean);
  const cards = Array.from(document.querySelectorAll('.joblist-box__item'));
  const items = cards.map((card) => {
    const titleLink = card.querySelector('.jobinfo__name');
    const href = titleLink?.href || '';
    const info = texts(card, '.jobinfo__other-info-item');
    const jobId = (href.match(/jobdetail\/([^/?#]+)/i) || [])[1] || href;
    return {
      jobId,
      jobName: clean(titleLink?.textContent),
      companyName: text(card, '.companyinfo__name'),
      city: info[0] || '',
      salary: text(card, '.jobinfo__salary'),
      workingExp: info[1] || '',
      eduLevel: info[2] || '',
      positionURL: href,
      skills: texts(card, '.jobinfo__tag .joblist-box__item-tag'),
      companyTags: texts(card, '.companyinfo__tag .joblist-box__item-tag'),
      jobType: /实习|intern/i.test(clean(titleLink?.textContent)) ? '实习' : '',
    };
  }).filter((item) => item.jobName && item.positionURL);
  const body = clean(document.body?.innerText);
  return JSON.stringify({
    items,
    noResults: /很抱歉.*职位.*找不到|暂无相关职位/.test(body),
    blocked: /Security Verification|安全验证|访问过于频繁/.test(body),
    loginLimited: items.length === 0 && /登录之后再搜索/.test(body),
  });
})()"""


class ZhilianCdpConnector:
    """Read the current public 智联 search cards in local Chrome."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "智联招聘",
        cdp_port: int = DEFAULT_CDP_PORT,
        session_factory: Callable[[int], Any] | None = None,
        settle_seconds: float = 2.0,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port
        self.session_factory = session_factory or _CDPSession
        self.settle_seconds = settle_seconds

    def _city_id(self) -> str:
        return ZHILIAN_CITY_CODES.get(self.city, "")

    def _search_url(self) -> str:
        return f"{_SEED_URL}?jl={self._city_id()}&kw={quote(self.keyword)}"

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
            time.sleep(self.settle_seconds)
            self._wait_results(cdp, sid)
            raw = cdp.eval_js(_DOM_EXTRACT_JS, sid)
            result = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(result, dict):
                raise ZhilianBlockedError(f"智联页面提取失败：返回格式异常 {result!r}")
            if result.get("blocked") or result.get("loginLimited"):
                raise ZhilianBlockedError("智联公开搜索页要求完成浏览器安全校验")
            items = result.get("items") or []
            if not items and not result.get("noResults"):
                raise ZhilianBlockedError("智联公开搜索页未返回可解析岗位卡")
            return [
                _to_record(item, self.source_name)
                for item in items
                if isinstance(item, dict)
            ]
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
        raise ZhilianError("智联页面加载超时")

    @staticmethod
    def _wait_results(cdp: Any, sid: str, timeout_seconds: float = 10) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            ready = cdp.eval_js(
                "document.querySelectorAll('.joblist-box__item').length > 0 || "
                "/很抱歉.*职位.*找不到|暂无相关职位|登录之后再搜索|安全验证/"
                ".test(document.body?.innerText || '')",
                sid,
            )
            if ready:
                return
            time.sleep(0.25)
