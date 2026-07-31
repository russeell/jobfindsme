"""Pure-HTTP connectors for 猎聘 / 前程无忧 / 智联招聘 (no Chrome needed).

These connectors talk to the platforms' own JSON APIs directly via
``curl_cffi`` with a Chrome TLS fingerprint — sub-second per source,
vs 6-8s for the CDP path.  Verified live 2026-07-31:

- 猎聘  ``api-c.liepin.com`` — works anonymously: XSRF-TOKEN cookie +
  ``X-Fscp-*`` headers (recipe from public open-source crawlers).
- 前程无忧 ``we.51job.com/api/job/search-pc`` — gated by Aliyun WAF.
  The v1 challenge (``var arg1='...'``) is solved locally via the
  well-known unsbox+hexXor algorithm; the newer WAF2 JS challenge
  cannot be solved without a browser, so we detect it and raise
  ``PureHttpBlockedError`` for discovery to fall back to CDP
  interception.
- 智联  ``fe-api.zhaopin.com/c/i/sou`` — returns a honeypot response
  (HTTP 200, ``results: []``, ``numFound: 999999``) unless the request
  carries a JS-generated fingerprint.  Detected and raised as
  ``PureHttpBlockedError`` so discovery falls back.

Every failure here is *loud* (typed exceptions), never a silent empty
list — discovery chains these before the CDP connectors and falls back
automatically, so a blocked pure-HTTP attempt costs ~0.3s.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import quote

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.china_platforms import LIEPIN_CITY_CODES
from jobfindsme.connectors.http_platforms import (
    WUYOU_CITY_CODES,
    ZHILIAN_CITY_CODES,
)
from jobfindsme.contracts import SourceKind


class PureHttpError(RuntimeError):
    """Pure-HTTP fetch failed at transport level (caller should fall back)."""


class PureHttpUnavailableError(PureHttpError):
    """curl_cffi is not installed — pure-HTTP path cannot run at all."""


class PureHttpBlockedError(PureHttpError):
    """The platform's anti-bot wall answered instead of the API
    (Aliyun WAF2 challenge, zhilian honeypot, liepin flag != 1)."""


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
            "curl_cffi is not installed; install jobfindsme[browser]"
        ) from error
    # Chrome TLS/JA3 fingerprint — plain requests/urllib are soft-blocked
    # by all three platforms even with a browser User-Agent.
    return curl_requests.Session(impersonate="chrome")


# ── Aliyun WAF v1 challenge (acw_sc__v2) ─────────────────────────────────────
#
# Served by we.51job.com to some clients/IPs.  The obfuscated JS on the
# challenge page computes: unsbox(arg1) then hex-XOR with a fixed key and
# sets the result as cookie `acw_sc__v2`, then reloads.  The algorithm is
# stable and widely re-implemented in open-source 51job crawlers.

_ACW_BOX = [
    0xF,
    0x23,
    0x1D,
    0x18,
    0x21,
    0x10,
    0x1,
    0x26,
    0xA,
    0x9,
    0x13,
    0x1F,
    0x28,
    0x1B,
    0x16,
    0x17,
    0x19,
    0xD,
    0x6,
    0xB,
    0x27,
    0x12,
    0x14,
    0x8,
    0xE,
    0x15,
    0x20,
    0x1A,
    0x2,
    0x1E,
    0x7,
    0x4,
    0x11,
    0x5,
    0x3,
    0x1C,
    0x22,
    0x25,
    0xC,
    0x24,
]
_ACW_KEY = "3000176000856006061501533003690027800375"


def acw_sc_v2(arg1: str) -> str:
    """Solve the Aliyun WAF v1 cookie from the 40-hex-char ``arg1``."""
    if len(arg1) != 40:
        raise ValueError("arg1 must be 40 hex characters")
    unboxed = [""] * 40
    for index, char in enumerate(arg1):
        for slot in range(40):
            if _ACW_BOX[slot] == index + 1:
                unboxed[slot] = char
    data = "".join(unboxed)
    return "".join(
        f"{int(data[i : i + 2], 16) ^ int(_ACW_KEY[i : i + 2], 16):02x}"
        for i in range(0, 40, 2)
    )


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

    def fetch(self) -> list[RawJobRecord]:
        dq = LIEPIN_CITY_CODES.get(self.city, "")
        search_url = f"https://www.liepin.com/zhaopin/?key={quote(self.keyword)}"
        if dq:
            search_url += f"&dqs={dq}"

        session = self._session_factory()
        try:
            session.get(search_url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
            xsrf = session.cookies.get("XSRF-TOKEN", "")
            if not xsrf:
                raise PureHttpBlockedError(
                    "liepin landing page did not set XSRF-TOKEN cookie"
                )
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
                            "currentPage": 0,
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
                timeout=_TIMEOUT,
            )
        except PureHttpError:
            raise
        except Exception as error:  # network / TLS / JSON decode
            raise PureHttpError(
                f"liepin pure-http transport failed: {error}"
            ) from error

        try:
            data = response.json()
        except Exception as error:
            raise PureHttpBlockedError(
                f"liepin returned non-JSON (status {response.status_code})"
            ) from error

        if data.get("flag") != 1:
            raise PureHttpBlockedError(
                f"liepin api refused: flag={data.get('flag')} code={data.get('code')}"
            )
        cards = (data.get("data") or {}).get("data", {}).get("jobCardList") or []

        records: list[RawJobRecord] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            job = card.get("job") or {}
            comp = card.get("comp") or {}
            title = str(job.get("title", ""))
            if not title:
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
                        "recruitment_track": "social",
                        "employment_type": "full_time",
                    },
                )
            )
        return records


# ── 前程无忧 (51job) ─────────────────────────────────────────────────────────

_WUYOU_API = "https://we.51job.com/api/job/search-pc"
_WUYOU_MAX_ATTEMPTS = 3


class WuyouPureHttpConnector:
    """51job search-pc direct API with an embedded Aliyun WAF v1 solver.

    Works when the WAF serves the classic ``arg1`` challenge (or no
    challenge).  When the newer WAF2 JS challenge is served instead
    (IP/client dependent — observed from a residential CN IP 2026-07),
    raises ``PureHttpBlockedError`` so discovery falls back to the CDP
    passive-interception connector.
    """

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
        city_code = WUYOU_CITY_CODES.get(self.city, "000000")
        search_url = (
            "https://we.51job.com/pc/search"
            f"?keyword={quote(self.keyword)}&jobArea={city_code}"
        )
        params = {
            "api_key": "51job",
            "timestamp": str(int(time.time())),
            "keyword": self.keyword,
            "searchType": "2",
            "function": "",
            "industry": "",
            "jobArea": city_code,
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
            "requestId": "",
            "pageSize": "20",
            "source": "1",
            "accountId": "",
            "pageCode": "sou|sou|soulb",
        }
        headers = {"User-Agent": _UA, "Referer": search_url}

        session = self._session_factory()
        try:
            for _ in range(_WUYOU_MAX_ATTEMPTS):
                response = session.get(
                    _WUYOU_API, params=params, headers=headers, timeout=_TIMEOUT
                )
                text = response.text or ""
                if "application/json" in response.headers.get("Content-Type", ""):
                    return self._parse(response.json(), search_url)
                arg1 = _extract_waf_arg1(text)
                if arg1 is not None:
                    session.cookies.set(
                        "acw_sc__v2", acw_sc_v2(arg1), domain="we.51job.com"
                    )
                    continue
                # Anything else is the WAF2 JS challenge or a block page —
                # not solvable without a browser.
                raise PureHttpBlockedError(
                    "51job served Aliyun WAF2 challenge (needs browser)"
                )
        except PureHttpError:
            raise
        except Exception as error:
            raise PureHttpError(f"51job pure-http transport failed: {error}") from error
        raise PureHttpBlockedError("51job WAF challenge not resolved after retries")

    def _parse(self, data: dict[str, Any], search_url: str) -> list[RawJobRecord]:
        body = data.get("resultbody", data)
        if not isinstance(body, dict):
            return []
        jobs_raw = body.get("job", body.get("data", {}))
        if isinstance(jobs_raw, dict):
            jobs_raw = jobs_raw.get("items", jobs_raw)
        jobs = list(jobs_raw) if isinstance(jobs_raw, (list, dict)) else []
        if isinstance(jobs_raw, dict):
            jobs = list(jobs_raw.values())

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
                        item.get("provideSalaryString", item.get("salary", ""))
                    ),
                    "url": str(item.get("jobHref", item.get("url", ""))),
                    "apply_url": str(item.get("jobHref", item.get("url", ""))),
                },
            )
            for item in jobs
            if isinstance(item, dict) and (item.get("jobName") or item.get("title"))
        ]


def _extract_waf_arg1(html: str) -> str | None:
    import re

    match = re.search(r"var arg1='([0-9A-Fa-f]{40})';", html)
    return match.group(1) if match else None


# ── 智联招聘 ─────────────────────────────────────────────────────────────────

_ZHILIAN_API = "https://fe-api.zhaopin.com/c/i/sou"


class ZhilianPureHttpConnector:
    """智联 fe-api /c/i/sou direct GET.

    The API answers anonymous requests with a honeypot (HTTP 200,
    ``results: []`` + ``numFound: 999999``) unless the request carries a
    JS-generated client fingerprint.  We make one cheap attempt
    (~0.25s); the honeypot signature raises ``PureHttpBlockedError`` so
    discovery falls back to CDP passive interception, where the SPA
    computes the fingerprint itself.  A genuine empty result
    (``numFound: 0``) is trusted and returned as ``[]``.
    """

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
        city_param = f"&jl={city_id}" if city_id else ""
        search_url = (
            f"https://sou.zhaopin.com/?kw={quote(self.keyword)}&p=1{city_param}"
        )

        session = self._session_factory()
        try:
            session.get(search_url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
            response = session.get(
                _ZHILIAN_API,
                params={
                    "pageSize": 90,
                    "cityId": city_id,
                    "workExperience": -1,
                    "education": -1,
                    "companyType": -1,
                    "employmentType": -1,
                    "jobWelfareTag": -1,
                    "kw": self.keyword,
                    "kt": 3,
                    "lastUrlQuery": json.dumps(
                        {"jl": city_id, "kw": self.keyword, "kt": "3"}
                    ),
                },
                headers={
                    "User-Agent": _UA,
                    "Referer": search_url,
                    "Origin": "https://sou.zhaopin.com",
                    "Accept": "application/json, text/plain, */*",
                },
                timeout=_TIMEOUT,
            )
            data = response.json()
        except PureHttpError:
            raise
        except Exception as error:
            raise PureHttpError(
                f"zhilian pure-http transport failed: {error}"
            ) from error

        payload = data.get("data", {}) if isinstance(data, dict) else {}
        results = payload.get("results") or []
        if not results and payload.get("numFound") == 999999:
            raise PureHttpBlockedError(
                "zhilian honeypot response (numFound=999999, results=[])"
            )

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
            for item in results
            if isinstance(item, dict) and (item.get("jobName") or item.get("title"))
        ]
