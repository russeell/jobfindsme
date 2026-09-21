"""Verified, bounded public company-career adapters."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.contracts import SourceKind


class CompanyCareerError(RuntimeError):
    pass


class TencentCareersConnector:
    """Tencent's public careers JSON list, including JD and stable pagination."""

    endpoint = "https://careers.tencent.com/tencentcareer/api/post/Query"

    def __init__(
        self,
        keyword: str,
        *,
        policy: ConnectorPolicy,
        opener: Callable[..., Any] = urllib.request.urlopen,
        page_size: int = 20,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")
        self.keyword = keyword.strip()
        self.opener = opener
        self.page_size = page_size

    def fetch_page(self, page: int = 1) -> tuple[list[RawJobRecord], int | None]:
        if not 1 <= page <= 200:
            raise ValueError("Tencent careers page must be between 1 and 200")
        query = urllib.parse.urlencode(
            {
                "timestamp": int(time.time() * 1000),
                "keyword": self.keyword,
                "pageIndex": page,
                "pageSize": self.page_size,
                "language": "zh-cn",
                "area": "cn",
            }
        )
        url = f"{self.endpoint}?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "JobFindsMe/desktop-company-careers"},
        )
        try:
            with self.opener(request, timeout=10) as response:
                payload = json.loads(response.read(2_000_000))
        except Exception as error:
            raise CompanyCareerError(
                f"Tencent careers request failed: {error}"
            ) from error
        if payload.get("Code") != 200 or not isinstance(payload.get("Data"), dict):
            raise CompanyCareerError("Tencent careers returned an invalid response")
        data = payload["Data"]
        posts = data.get("Posts") or []
        if not isinstance(posts, list):
            raise CompanyCareerError("Tencent careers posts are not a list")
        records = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            title = str(post.get("RecruitPostName") or "").strip()
            post_id = str(post.get("PostId") or "").strip()
            if not title or not post_id:
                continue
            detail_url = (
                f"https://careers.tencent.com/jobdesc.html?postId="
                f"{urllib.parse.quote(post_id)}"
            )
            responsibility = str(post.get("Responsibility") or "").strip()
            records.append(
                RawJobRecord(
                    source_kind=SourceKind.ATS,
                    source_name="腾讯招聘官网",
                    source_url=url,
                    external_id=post_id,
                    payload={
                        "title": title,
                        "company": str(post.get("ComName") or "腾讯").strip() or "腾讯",
                        "description": responsibility or title,
                        "location": str(post.get("LocationName") or "").strip(),
                        "url": detail_url,
                        "apply_url": detail_url,
                        "published_at": str(post.get("LastUpdateTime") or "").strip(),
                        "experience": str(
                            post.get("RequireWorkYearsName") or ""
                        ).strip(),
                        "detail_level": "structured_source",
                        "recruitment_track": "social",
                        "employment_type": "full_time",
                    },
                )
            )
        try:
            total = int(data.get("Count") or 0)
        except (TypeError, ValueError):
            total = 0
        next_page = page + 1 if page * self.page_size < total and records else None
        return records, next_page
