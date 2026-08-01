"""Source-side contracts: platforms, provenance, subscriptions, diagnostics.

These types describe where a job came from and how a source run behaved.
They are internal plumbing — user-facing docs and Agent conversations only
ever see the source line rendered by presentation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from jobfindsme.contracts.base import StrictModel


class SourceKind(StrEnum):
    URL = "url"
    CSV = "csv"
    JSON = "json"
    ATS = "ats"
    CAREER_SITE = "career_site"


class JobLiveness(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class JobDetailLevel(StrEnum):
    LIST_CARD = "list_card"
    DETAIL_PAGE = "detail_page"
    STRUCTURED_SOURCE = "structured_source"


class SourceEvidence(StrictModel):
    source_kind: SourceKind
    source_name: str = Field(min_length=1, max_length=120)
    source_url: str
    fetched_at: datetime
    published_at: datetime | None = None
    liveness: JobLiveness = JobLiveness.UNKNOWN
    detail_level: JobDetailLevel = JobDetailLevel.LIST_CARD
    description_source_url: str | None = None
    description_fetched_at: datetime | None = None

    @model_validator(mode="after")
    def validate_detail_provenance(self) -> Self:
        if self.detail_level is JobDetailLevel.DETAIL_PAGE and (
            not self.description_source_url or self.description_fetched_at is None
        ):
            raise ValueError(
                "detail_page evidence requires its source URL and fetched timestamp"
            )
        return self


class DiscoverySourceKind(StrEnum):
    BOSS_CDP = "boss_cdp"
    LIEPIN_HTTP = "liepin_http"
    # Remove after migration 013 and v1.0 support window.
    # Compatibility only: pre-v0.4.3 workspaces may still contain this value.
    LIEPIN_CDP = "liepin_cdp"
    # Remove after migration 013 and v1.0 support window.
    # Compatibility only: old workspaces may still contain these values.
    ZHILIAN_CDP = "zhilian_cdp"
    LAGOU_CDP = "lagou_cdp"
    WUYOU_CDP = "wuyou_cdp"
    JSON_FILE = "json_file"
    CSV_FILE = "csv_file"

    @property
    def retired(self) -> bool:
        return self in {self.ZHILIAN_CDP, self.LAGOU_CDP, self.WUYOU_CDP}

    @property
    def uses_browser(self) -> bool:
        # Liepin is pure HTTP (curl_cffi, no Chrome); CDP is only a fallback.
        return self in {
            self.BOSS_CDP,
            self.LIEPIN_CDP,
        }


class DiscoverySource(StrictModel):
    kind: DiscoverySourceKind
    source_name: str
    catalog_managed: bool = False
    location: str | None = None
    board_token: str | None = None
    board_name: str | None = None
    url: str | None = None
    path: str | None = None
    query: str | None = None
    site_key: str | None = None
    robots_allowed: bool = False

    @model_validator(mode="after")
    def validate_kind_fields(self) -> Self:
        required = {
            DiscoverySourceKind.BOSS_CDP: self.query,
            DiscoverySourceKind.LIEPIN_HTTP: self.query,
            DiscoverySourceKind.LIEPIN_CDP: self.query,
            DiscoverySourceKind.ZHILIAN_CDP: self.query,
            DiscoverySourceKind.LAGOU_CDP: self.query,
            DiscoverySourceKind.WUYOU_CDP: self.query,
            DiscoverySourceKind.JSON_FILE: self.path,
            DiscoverySourceKind.CSV_FILE: self.path,
        }[self.kind]
        if not required:
            raise ValueError(f"{self.kind} source is missing its locator")
        return self


class SourceRunStatus(StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceRunStats(StrictModel):
    """One source attempt captured by the live-search Loop."""

    source_name: str
    source_kind: DiscoverySourceKind
    status: SourceRunStatus
    elapsed_seconds: float = Field(ge=0)
    discovered: int = Field(default=0, ge=0)
    unique: int = Field(default=0, ge=0)
    versions_created: int = Field(default=0, ge=0)
    cache_used: bool = False
    error: str | None = Field(default=None, max_length=1000)


class SourceHealth(StrEnum):
    NEVER_CHECKED = "never_checked"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class SourceSubscription(StrictModel):
    subscription_id: str
    workspace_id: str
    plan_id: str
    source: DiscoverySource
    enabled: bool = True
    health_status: SourceHealth = SourceHealth.NEVER_CHECKED
    last_checked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class SourceLink(StrictModel):
    name: str
    category: str
    url: str
    access_mode: str
    note: str = ""


class JobSourceRecord(StrictModel):
    record_id: str
    workspace_id: str
    job_id: str
    source_name: str
    external_id: str
    source_url: str
    apply_url: str
    liveness: JobLiveness
    observed_at: datetime
