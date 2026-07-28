"""Playwright-based connector for SPA career sites that lack public APIs.

Uses headless Chromium to render SPA pages, intercept internal job search
API responses, and extract structured job records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.contracts import SourceKind


@dataclass(frozen=True)
class SpaSiteConfig:
    """Configuration for one SPA career site."""

    source_name: str
    search_url_template: str
    api_url_pattern: str
    job_list_key: str
    external_id_field: str = "id"
    title_field: str = "title"
    location_field: str = "location"
    description_field: str = "description"
    company_name: str = ""


# ── Site registry ────────────────────────────────────────────────────────────

SITE_REGISTRY: dict[str, SpaSiteConfig] = {
    "bytedance": SpaSiteConfig(
        source_name="字节跳动",
        search_url_template=(
            "https://jobs.bytedance.com/experienced/position"
            "?keywords={keyword}&location={location}&limit=10"
        ),
        api_url_pattern=r"search/job/posts",
        job_list_key="job_post_list",
        external_id_field="id",
        title_field="title",
        location_field="city_info",
        description_field="description",
        company_name="字节跳动",
    ),
    "meituan": SpaSiteConfig(
        source_name="美团",
        search_url_template=(
            "https://zhaopin.meituan.com/web/campus?keyword={keyword}"
        ),
        api_url_pattern=r"job/getJobList",
        job_list_key="list",
        external_id_field="jobUnionId",
        title_field="name",
        location_field="cityList",
        description_field="desc",
        company_name="美团",
    ),
    "didi": SpaSiteConfig(
        source_name="滴滴",
        search_url_template=("https://talent.didiglobal.com/social?keyword={keyword}"),
        api_url_pattern=r"job/front/list",
        job_list_key="items",
        external_id_field="jdId",
        title_field="jobName",
        location_field="workArea",
        description_field="jobDuty",
        company_name="滴滴",
    ),
    "bilibili": SpaSiteConfig(
        source_name="哔哩哔哩",
        search_url_template=("https://jobs.bilibili.com/social?keyword={keyword}"),
        api_url_pattern=r"position/positionList",
        job_list_key="list",
        external_id_field="id",
        title_field="positionName",
        location_field="cityName",
        description_field="description",
        company_name="哔哩哔哩",
    ),
}


# ── Connector ────────────────────────────────────────────────────────────────


class PlaywrightSpaConnector:
    """Discover jobs from SPA career sites via headless browser."""

    def __init__(
        self,
        site_key: str,
        keyword: str,
        *,
        policy: ConnectorPolicy,
        source_name: str | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        config = SITE_REGISTRY.get(site_key)
        if config is None:
            raise ValueError(f"unknown SPA site: {site_key}")
        self.config = config
        self.keyword = keyword.strip()
        if not self.keyword or len(self.keyword) > 100:
            raise ValueError("invalid keyword")
        self.source_name = source_name or config.source_name

    def fetch(self) -> list[RawJobRecord]:
        """Launch headless browser and extract job records."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright not installed. Run: pip install playwright && "
                "python -m playwright install chromium"
            ) from exc

        cfg = self.config
        url = cfg.search_url_template.format(keyword=self.keyword, location="")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            collected: list[dict[str, Any]] = []

            def on_response(resp):
                if resp.status != 200:
                    return
                if not re.search(cfg.api_url_pattern, resp.url):
                    return
                ct = resp.headers.get("content-type", "")
                if "json" not in ct:
                    return
                try:
                    body = resp.json()
                except Exception:
                    return
                jobs = _extract_job_list(body, cfg.job_list_key)
                if jobs:
                    collected.extend(jobs)

            page.on("response", on_response)
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            browser.close()

        return [
            self._to_record(job, url)
            for job in collected
            if isinstance(job, dict) and job.get(cfg.external_id_field)
        ]

    def _to_record(self, job: dict[str, Any], source_url: str) -> RawJobRecord:
        cfg = self.config
        external_id = str(job[cfg.external_id_field])

        loc = job.get(cfg.location_field)
        if isinstance(loc, dict):
            location = loc.get("name") or loc.get("cityName") or ""
        elif isinstance(loc, list) and loc:
            location = ",".join(
                str(item.get("name", item)) if isinstance(item, dict) else str(item)
                for item in loc
            )
        else:
            location = str(loc) if loc else ""

        title = str(job.get(cfg.title_field, ""))
        description = str(job.get(cfg.description_field, ""))

        return RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name=self.source_name,
            source_url=source_url,
            external_id=external_id,
            payload={
                "title": title,
                "company": cfg.company_name,
                "description": description,
                "location": location,
                "url": source_url,
                "apply_url": source_url,
            },
        )


def _extract_job_list(body: Any, key: str) -> list[dict[str, Any]]:
    """Walk a JSON response to find the job list at any nesting level."""
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]

    if not isinstance(body, dict):
        return []

    # Direct match
    jobs = body.get(key)
    if isinstance(jobs, list):
        return [item for item in jobs if isinstance(item, dict)]

    # Check nested under common wrapper keys
    for wrapper in ("data", "result", "content"):
        inner = body.get(wrapper)
        if isinstance(inner, dict):
            jobs = inner.get(key)
            if isinstance(jobs, list):
                return [item for item in jobs if isinstance(item, dict)]

    return []
