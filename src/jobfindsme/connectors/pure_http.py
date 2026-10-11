"""Pure-HTTP 猎聘 connector used by the maintained four-source product."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import quote

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.china_platforms import LIEPIN_CITY_CODES
from jobfindsme.contracts import SourceKind


class PureHttpError(RuntimeError):
    """Safe, classified failure; never include upstream bodies or credentials."""

    code = "source_unavailable"

    def __init__(self, message: str, *, code: str | None = None):
        self.code = code or self.code
        super().__init__(f"{self.code}:{message}")


class PureHttpUnavailableError(PureHttpError):
    """curl_cffi is not installed — pure-HTTP path cannot run at all."""


class PureHttpBlockedError(PureHttpError):
    """The remote endpoint rejected or challenged the request."""


class PureHttpContractError(PureHttpError):
    code = "source_contract_error"


def check_response(response: Any) -> None:
    status = response.status_code
    if status == 401:
        raise PureHttpBlockedError("来源要求登录，请在原页确认", code="login_required")
    if status in (403, 429):
        raise PureHttpBlockedError(
            "来源限制访问，请在原页处理后重试", code="risk_control"
        )
    if status >= 500:
        raise PureHttpError("来源服务暂不可用，请稍后重试")
    if status >= 400:
        raise PureHttpError("来源拒绝本次请求，请检查来源")


def liepin_cards(response: Any) -> list[dict]:
    check_response(response)
    try:
        data = response.json()
    except Exception as error:
        if any(
            word in response.text[:10000].lower()
            for word in ("captcha", "验证码", "安全验证", "访问过于频繁")
        ):
            raise PureHttpBlockedError("来源要求验证", code="risk_control") from error
        raise PureHttpContractError("未取得预期的岗位数据，请检查来源") from error
    if not isinstance(data, dict):
        raise PureHttpContractError("岗位响应结构已变化")
    if data.get("flag") != 1:
        # Unknown business codes are not proof that a session needs verification.
        raise PureHttpBlockedError("来源未接受本次检索，请稍后检查来源")
    outer = data.get("data")
    inner = outer.get("data") if isinstance(outer, dict) else None
    cards = inner.get("jobCardList") if isinstance(inner, dict) else None
    if not isinstance(cards, list):
        raise PureHttpContractError("岗位列表字段缺失或格式变化，不代表没有岗位")
    return cards


class _Response(Protocol):
    status_code: int
    headers: Any
    text: str

    def json(self) -> Any: ...


class _Session(Protocol):
    cookies: Any

    def get(self, url: str, **kwargs: Any) -> _Response: ...

    def post(self, url: str, **kwargs: Any) -> _Response: ...


SessionFactory = Callable[[], _Session]

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_TIMEOUT = 10


def _default_session_factory() -> _Session:
    try:
        from curl_cffi import requests as curl_requests
    except ImportError as error:
        raise PureHttpUnavailableError(
            "curl_cffi is not installed; install the optional browser dependencies"
        ) from error
    # Chrome TLS/JA3 fingerprint — plain requests/urllib are soft-blocked
    # by all three platforms even with a browser User-Agent.
    return curl_requests.Session(impersonate="chrome")


# ── 猎聘 ─────────────────────────────────────────────────────────────────────

_LIEPIN_API = "https://api-c.liepin.com/api/com.liepin.searchfront4c.pc-search-job"


class LiepinPureHttpConnector:
    """猎聘 search via the official web JSON API — verified ~0.9s, 40+ jobs.

    Flow: GET the search page once to obtain the ``XSRF-TOKEN`` cookie,
    then POST the search query with the ``X-Fscp-*`` header set the SPA
    sends.  No login, no signature reverse-engineering.
    """

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "猎聘",
        session_factory: SessionFactory | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.source_name = source_name
        self._session_factory = session_factory or _default_session_factory
        self._session: _Session | None = None
        self._session_at = 0.0
        self._lock = threading.Lock()
        self.deadline: float | None = None

    def _timeout(self) -> float:
        remaining = (
            _TIMEOUT if self.deadline is None else self.deadline - time.monotonic()
        )
        if remaining <= 0:
            raise PureHttpError("本轮读取预算已用完", code="source_timeout")
        return min(_TIMEOUT, remaining)

    def close(self) -> None:
        session, self._session = self._session, None
        close = getattr(session, "close", None)
        if close:
            close()

    def fetch(self) -> list[RawJobRecord]:
        records, _next_page = self.fetch_page(0)
        return records

    def fetch_page(
        self, current_page: int = 0
    ) -> tuple[list[RawJobRecord], int | None]:
        with self._lock:
            try:
                return self._fetch_page(current_page)
            except Exception:
                self.close()
                raise

    def _fetch_page(self, current_page: int) -> tuple[list[RawJobRecord], int | None]:
        if not 0 <= current_page <= 200:
            raise ValueError("liepin page must be between 0 and 200")
        dq = LIEPIN_CITY_CODES.get(self.city, "")
        if self.city and not dq:
            raise ValueError(f"unsupported_city:猎聘尚未核验城市「{self.city}」编码")
        search_url = f"https://www.liepin.com/zhaopin/?key={quote(self.keyword)}"
        if dq:
            search_url += f"&dqs={dq}"

        if self._session is not None and time.monotonic() - self._session_at >= 120:
            self.close()
        if self._session is None:
            self._session = self._session_factory()
            self._session_at = time.monotonic()
        session = self._session
        try:
            if not session.cookies.get("XSRF-TOKEN", ""):
                landing = session.get(
                    search_url, headers={"User-Agent": _UA}, timeout=self._timeout()
                )
                check_response(landing)
            xsrf = session.cookies.get("XSRF-TOKEN", "")
            if not xsrf:
                raise PureHttpBlockedError("来源初始化未完成，请检查原页后重试")
            response = session.post(
                _LIEPIN_API,
                headers={
                    "User-Agent": _UA,
                    "Content-Type": "application/json;charset=UTF-8",
                    "X-Client-Type": "web",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Fscp-Bi-Stat": json.dumps({"location": search_url}),
                    "X-Fscp-Fe-Version": "",
                    "X-Fscp-Std-Info": json.dumps({"client_id": "40108"}),
                    "X-Fscp-Trace-Id": str(uuid.uuid4()),
                    "X-Fscp-Version": "1.1",
                    "X-XSRF-TOKEN": xsrf,
                    "Origin": "https://www.liepin.com",
                    "Referer": search_url,
                },
                json={
                    "data": {
                        "mainSearchPcConditionForm": {
                            "city": dq,
                            "dq": dq,
                            "pubTime": "",
                            "currentPage": current_page,
                            "pageSize": 40,
                            "key": self.keyword,
                            "suggestTag": "",
                            "workYearCode": "0",
                            "compId": "",
                            "compName": "",
                            "compTag": "",
                            "industry": "",
                            "salaryCode": "",
                            "jobKind": "",
                            "compScale": "",
                            "compKind": "",
                            "compStage": "",
                            "eduLevel": "",
                            "salaryLow": "",
                            "salaryHigh": "",
                        },
                        "passThroughForm": {
                            "scene": "input",
                            "skId": uuid.uuid4().hex,
                            "fkId": uuid.uuid4().hex,
                            "ckId": uuid.uuid4().hex,
                        },
                    }
                },
                timeout=self._timeout(),
            )
        except PureHttpError:
            raise
        except Exception as error:  # network / TLS / JSON decode
            raise PureHttpError("来源连接失败，请稍后重试") from error

        cards = liepin_cards(response)

        records: list[RawJobRecord] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            job = card.get("job") or {}
            comp = card.get("comp") or {}
            if not isinstance(job, dict) or not isinstance(comp, dict):
                continue
            title = job.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            job_id = str(job.get("jobId", ""))
            link = str(job.get("link", ""))
            # Compose description from structured requirement fields
            # to give the ranker signal beyond the title alone.
            desc_parts = [str(job.get("title", ""))]
            work_years = str(job.get("requireWorkYears", ""))
            if work_years:
                desc_parts.append(f"经验要求:{work_years}")
            edu = str(job.get("requireEduLevel", ""))
            if edu:
                desc_parts.append(f"学历要求:{edu}")
            labels = job.get("labels") or []
            if labels:
                tag_text = "、".join(str(label) for label in labels[:8])
                desc_parts.append("技能标签:" + tag_text)
            industry = str(comp.get("compIndustry", ""))
            if industry:
                desc_parts.append(f"行业:{industry}")
            description = "；".join(desc_parts)
            if len(description) < 20:
                description = title  # fallback: use title as description
            records.append(
                RawJobRecord(
                    source_kind=SourceKind.CAREER_SITE,
                    source_name=self.source_name,
                    source_url=search_url,
                    external_id=job_id or link or title,
                    payload={
                        "title": title,
                        "company": str(comp.get("compName", "")),
                        "description": description,
                        "location": str(job.get("dq", "")),
                        "salary": str(job.get("salary", "")),
                        "url": link,
                        "apply_url": link,
                        "recruitment_track": "unknown",
                        "employment_type": "unknown",
                    },
                )
            )
        if cards and not records:
            raise PureHttpContractError("岗位卡片均未能解析，不代表没有岗位")
        return records, current_page + 1 if len(cards) >= 40 else None
