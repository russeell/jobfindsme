"""Domain models: workspace, sources, jobs, salary, match evidence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base contract that rejects accidental or misspelled fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Workspace(StrictModel):
    workspace_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    created_at: datetime


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
    ZHILIAN_HTTP = "zhilian_http"
    WUYOU_HTTP = "wuyou_http"
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
            DiscoverySourceKind.ZHILIAN_HTTP: self.query,
            DiscoverySourceKind.WUYOU_HTTP: self.query,
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


class RecruitmentTrack(StrEnum):
    CAMPUS = "campus"
    SOCIAL = "social"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class SalaryPeriod(StrEnum):
    MONTH = "month"
    YEAR = "year"
    DAY = "day"
    HOUR = "hour"
    UNKNOWN = "unknown"


class Salary(StrictModel):
    """The single salary truth for a job.

    Raw/structured salary is the fact; monthly K values are computed
    projections, never a second stored truth.
    """

    raw_text: str
    currency: str | None = None
    period: SalaryPeriod = SalaryPeriod.UNKNOWN
    min_amount: int | None = Field(default=None, ge=0)
    max_amount: int | None = Field(default=None, ge=0)
    months_per_year: int | None = Field(default=None, ge=1, le=24)
    normalized_annual_min: int | None = Field(default=None, ge=0)
    normalized_annual_max: int | None = Field(default=None, ge=0)

    @property
    def monthly_min_k(self) -> int | None:
        """Conservative monthly lower bound in K, or None when not comparable."""
        if self.currency not in {None, "CNY"} or self.min_amount is None:
            return None
        if self.period is SalaryPeriod.MONTH:
            return self.min_amount // 1000
        if self.period is SalaryPeriod.YEAR:
            return self.min_amount // 1000 // 12
        return None

    @property
    def monthly_max_k(self) -> int | None:
        """Conservative monthly upper bound in K, or None when not comparable."""
        if self.currency not in {None, "CNY"} or self.max_amount is None:
            return None
        if self.period is SalaryPeriod.MONTH:
            return self.max_amount // 1000
        if self.period is SalaryPeriod.YEAR:
            return self.max_amount // 1000 // 12
        return None


# Backwards-compatible name for clients imported before the Step-1 rename.
SalaryDetails = Salary


class JobPosting(StrictModel):
    job_id: str = Field(min_length=1, max_length=128)
    external_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    description: str = ""
    locations: tuple[str, ...] = ()
    # Legacy mirrors of salary.monthly_min_k/max_k, kept for DB/presentation
    # compatibility.  The canonical truth is the `salary` field.
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    salary: Salary | None = None
    experience_min_years: int | None = Field(default=None, ge=0, le=80)
    experience_max_years: int | None = Field(default=None, ge=0, le=80)
    recruitment_track: RecruitmentTrack = RecruitmentTrack.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    apply_url: str
    fingerprint: str = Field(min_length=16, max_length=128)
    content_hash: str = Field(min_length=16, max_length=128)
    source: SourceEvidence

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if (
            self.salary_min_k is not None
            and self.salary_max_k is not None
            and self.salary_min_k > self.salary_max_k
        ):
            raise ValueError("salary_min_k cannot exceed salary_max_k")
        if (
            self.experience_min_years is not None
            and self.experience_max_years is not None
            and self.experience_min_years > self.experience_max_years
        ):
            raise ValueError("experience_min_years cannot exceed experience_max_years")
        return self


class MatchEvidence(StrictModel):
    hard_filter_passed: bool
    matched_terms: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_pairs: tuple[EvidencePair, ...] = ()
    matched_profile_skills: tuple[str, ...] = ()
    missing_job_skills: tuple[str, ...] = ()
    missing_required_skills: tuple[str, ...] = ()
    extracted_signals: dict = Field(default_factory=dict)


class EvidencePair(StrictModel):
    criterion: str
    profile_evidence: str
    job_evidence: str


class JobSummary(StrictModel):
    job_id: str
    title: str
    company: str
    locations: tuple[str, ...] = ()
    salary: Salary | None = None
    recruitment_track: RecruitmentTrack = RecruitmentTrack.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    apply_url: str
    source_name: str
    liveness: JobLiveness
    description_excerpt: str = Field(default="", max_length=400)
    untrusted_external_content: bool = True


class JobMatchSummary(StrictModel):
    job: JobSummary
    score: float = Field(ge=0, le=1)
    evidence: MatchEvidence


class JobDetails(StrictModel):
    job: JobPosting
    source_records: tuple[JobSourceRecord, ...] = ()
    untrusted_external_content: bool = True
    description_truncated: bool = False
