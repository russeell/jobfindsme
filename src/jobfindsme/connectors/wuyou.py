"""前程无忧 connector via the SPA search JSON API (pure HTTP).

The 51job SPA calls we.51job.com/api/job/search-pc.  The endpoint sits
behind Aliyun WAF: clean requests return the JSON payload, while suspicious
ones (datacenter IPs, missing browser fingerprint) receive an HTML
challenge.  We detect the challenge explicitly and report it as blocked
instead of pretending the platform had no jobs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlencode

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
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
        params = {
            "keyword": self.keyword,
            "searchType": "2",
            "sortType": "0",
            "jobArea": WUYOU_CITY_CODES.get(self.city, ""),
            "pageNum": "1",
            "pageSize": "30",
        }
        url = f"{_API_URL}?{urlencode(params)}"
        session = self._session_factory()
        try:
            response = session.get(
                url,
                headers={
                    "User-Agent": _UA,
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://we.51job.com/",
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
        items = ((payload.get("resultbody") or {}).get("job") or {}).get("items") or []
        return [
            self._to_record(item)
            for item in items
            if isinstance(item, dict) and item.get("jobid")
        ]

    def _to_record(self, item: dict[str, Any]) -> RawJobRecord:
        title = str(item.get("job_name") or "")
        link = str(item.get("job_href") or "")
        if link.startswith("//"):
            link = "https:" + link
        elif link.startswith("/"):
            link = "https://www.51job.com" + link
        classification = " ".join(
            (title, str(item.get("jobtype_text") or ""))
        ).casefold()
        recruitment_track = (
            "campus"
            if any(t in classification for t in ("校招", "校园", "应届"))
            else "social"
        )
        job_type = str(item.get("jobtype_text") or "").casefold()
        employment_type = (
            "internship"
            if "实习" in job_type or "intern" in job_type
            else "part_time"
            if "兼职" in job_type
            else "contract"
            if "合同" in job_type
            else "full_time"
        )
        description = " ".join(
            part
            for part in (
                str(item.get("jobtype_text") or ""),
                str(item.get("jobwelf") or ""),
                str(item.get("companytype_text") or ""),
            )
            if part
        )
        return RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name=self.source_name,
            source_url=link or _API_URL,
            external_id=str(item.get("jobid") or ""),
            payload={
                "title": title,
                "company": str(item.get("company_name") or ""),
                "description": description,
                "location": str(item.get("workarea_text") or ""),
                "salary": str(item.get("providesalary_text") or ""),
                "experience": "",
                "degree": "",
                "skills": "",
                "url": link,
                "apply_url": link,
                "recruitment_track": recruitment_track,
                "employment_type": employment_type,
                "welfare": str(item.get("jobwelf") or ""),
                "published_at": str(
                    item.get("issue_date") or item.get("updatedate") or ""
                ),
            },
        )
