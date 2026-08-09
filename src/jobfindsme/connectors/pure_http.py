"""Pure-HTTP 猎聘 connector used by the maintained four-source product."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import quote

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.china_platforms import LIEPIN_CITY_CODES
from jobfindsme.contracts import SourceKind


class PureHttpError(RuntimeError):
    """Pure-HTTP fetch failed at transport level (caller should fall back)."""


class PureHttpUnavailableError(PureHttpError):
    """curl_cffi is not installed — pure-HTTP path cannot run at all."""


class PureHttpBlockedError(PureHttpError):
    """The remote endpoint rejected or challenged the request."""


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
