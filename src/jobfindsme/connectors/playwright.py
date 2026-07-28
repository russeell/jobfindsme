"""Playwright-based connector for SPA career sites that lack public APIs.

Uses headless Chromium to render SPA pages, intercept internal job search
API responses, and extract structured job records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote_plus

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
    recruitment_track: str = "unknown"
    detail_url_template: str | None = None


class SpaBrowser(Protocol):
    """Small browser boundary that keeps source mapping deterministic in tests."""

    def collect(self, config: SpaSiteConfig, url: str) -> list[dict[str, Any]]: ...


class PlaywrightBrowser:
    """Collect matching JSON responses from one rendered career page."""

    def collect(self, config: SpaSiteConfig, url: str) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                'Playwright is unavailable. Install "jobfindsme[browser]" and run '
                "python -m playwright install chromium."
            ) from exc

        collected: list[dict[str, Any]] = []
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                raise RuntimeError(
                    "Playwright Chromium is unavailable or failed to start. "
                    "Run 'python -m playwright install chromium'. JobFindsMe "
                    "will not fall back to your system Google Chrome."
                ) from error
            try:
                page = browser.new_page()

                def on_response(response: Any) -> None:
                    if response.status != 200:
                        return
                    if not re.search(config.api_url_pattern, response.url):
                        return
                    content_type = response.headers.get("content-type", "")
                    if "json" not in content_type:
                        return
                    try:
                        body = response.json()
                    except Exception:
                        return
                    collected.extend(_extract_job_list(body, config.job_list_key))

                page.on("response", on_response)
                # Some career SPAs keep the document lifecycle open while loading
                # analytics. "commit" is enough because the useful contract is the
                # intercepted JSON response, not a fully settled visual page.
                page.goto(url, timeout=30_000, wait_until="commit")
                page.wait_for_timeout(8_000)
            finally:
                browser.close()
        return collected


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
        recruitment_track="social",
        detail_url_template=(
            "https://jobs.bytedance.com/experienced/position/{external_id}/detail"
        ),
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
        recruitment_track="campus",
        detail_url_template=(
            "https://zhaopin.meituan.com/web/position/detail"
            "?jobUnionId={external_id}&highlightType=campus"
        ),
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
        recruitment_track="social",
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
        recruitment_track="social",
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
        browser: SpaBrowser | None = None,
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
        self.browser = browser or PlaywrightBrowser()

    def fetch(self) -> list[RawJobRecord]:
        """Render one source and convert unique response entries into records."""
        cfg = self.config
        url = cfg.search_url_template.format(
            keyword=quote_plus(self.keyword),
            location="",
        )
        collected = self.browser.collect(cfg, url)
        records: list[RawJobRecord] = []
        seen_ids: set[str] = set()
        for job in collected:
            external_id = str(job.get(cfg.external_id_field, "")).strip()
            if not external_id or external_id in seen_ids:
                continue
            seen_ids.add(external_id)
            records.append(self._to_record(job, url))
        return records

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
        detail_url = (
            cfg.detail_url_template.format(external_id=external_id)
            if cfg.detail_url_template
            else source_url
        )

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
                "url": detail_url,
                "apply_url": detail_url,
                "recruitment_track": cfg.recruitment_track,
            },
        )


def _extract_job_list(
    body: Any,
    key: str,
    *,
    _depth: int = 0,
) -> list[dict[str, Any]]:
    """Walk a JSON response to find the job list at any nesting level."""
    if _depth > 5:
        return []
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]

    if not isinstance(body, dict):
        return []

    # Direct match
    jobs = body.get(key)
    if isinstance(jobs, list):
        return [item for item in jobs if isinstance(item, dict)]

    # Check nested under common wrapper keys. Real SPA APIs often use more
    # than one wrapper, for example data.result.job_post_list.
    for wrapper in ("data", "result", "content"):
        inner = body.get(wrapper)
        if isinstance(inner, dict):
            jobs = _extract_job_list(inner, key, _depth=_depth + 1)
            if jobs:
                return jobs

    return []
