from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base contract that rejects accidental or misspelled fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Workspace(StrictModel):
    workspace_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    created_at: datetime


class SearchPlan(StrictModel):
    plan_id: str = Field(min_length=1, max_length=128)
    workspace_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    target_roles: tuple[str, ...] = Field(min_length=1)
    locations: tuple[str, ...] = ()
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    experience_min_years: int | None = Field(default=None, ge=0, le=80)
    experience_max_years: int | None = Field(default=None, ge=0, le=80)
    recruitment_track: RecruitmentTrack | None = None
    employment_type: EmploymentType | None = None
    official_sources_only: bool = True
    exclusions: tuple[str, ...] = ()
    created_at: datetime
    updated_at: datetime

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


class SalaryPeriod(StrEnum):
    MONTH = "month"
    YEAR = "year"
    DAY = "day"
    HOUR = "hour"
    UNKNOWN = "unknown"


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


class SalaryDetails(StrictModel):
    raw_text: str
    currency: str | None = None
    period: SalaryPeriod = SalaryPeriod.UNKNOWN
    min_amount: int | None = Field(default=None, ge=0)
    max_amount: int | None = Field(default=None, ge=0)
    months_per_year: int | None = Field(default=None, ge=1, le=24)
    normalized_annual_min: int | None = Field(default=None, ge=0)
    normalized_annual_max: int | None = Field(default=None, ge=0)


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


class JobPosting(StrictModel):
    job_id: str = Field(min_length=1, max_length=128)
    external_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    description: str = ""
    locations: tuple[str, ...] = ()
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    salary: SalaryDetails | None = None
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


class EvidencePair(StrictModel):
    criterion: str
    profile_evidence: str
    job_evidence: str


class JobStateKind(StrEnum):
    DISCOVERED = "discovered"
    SAVED = "saved"
    APPLIED = "applied"
    REJECTED = "rejected"


class JobChangeType(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    REOPENED = "reopened"
    UNCHANGED = "unchanged"


class JobMatch(StrictModel):
    job: JobPosting
    score: float = Field(ge=0, le=1)
    evidence: MatchEvidence
    state: JobStateKind = JobStateKind.DISCOVERED
    first_seen_at: datetime | None = None
    change_type: JobChangeType | None = None


class JobSummary(StrictModel):
    job_id: str
    title: str
    company: str
    locations: tuple[str, ...] = ()
    salary: SalaryDetails | None = None
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


class JobState(StrictModel):
    workspace_id: str
    job_id: str
    state: JobStateKind
    note: str = Field(default="", max_length=1000)
    updated_at: datetime


class DiscoverySourceKind(StrEnum):
    BOSS_CDP = "boss_cdp"
    LIEPIN_CDP = "liepin_cdp"
    ZHILIAN_CDP = "zhilian_cdp"
    LAGOU_CDP = "lagou_cdp"
    WUYOU_CDP = "wuyou_cdp"
    JSON_FILE = "json_file"
    CSV_FILE = "csv_file"

    @property
    def uses_browser(self) -> bool:
        return self in {
            self.BOSS_CDP,
            self.LIEPIN_CDP,
            self.ZHILIAN_CDP,
            self.LAGOU_CDP,
            self.WUYOU_CDP,
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


class SearchRefreshMode(StrEnum):
    """Control how much remote discovery an interactive search performs."""

    FAST = "fast"
    FULL = "full"
    CACHE = "cache"


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


class SearchRunDiagnostics(StrictModel):
    """Machine-generated timings and counts for one end-to-end search."""

    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float = Field(ge=0)
    matching_seconds: float = Field(ge=0)
    refresh_mode: SearchRefreshMode = SearchRefreshMode.FAST
    source_runs: tuple[SourceRunStats, ...] = ()
    total_discovered: int = Field(default=0, ge=0)
    total_unique: int = Field(default=0, ge=0)
    duplicates_removed: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    new_count: int = Field(default=0, ge=0)
    changed_count: int = Field(default=0, ge=0)
    reopened_count: int = Field(default=0, ge=0)
    closed_count: int = Field(default=0, ge=0)
    repeated_suppressed_count: int = Field(default=0, ge=0)
    low_relevance_filtered_count: int = Field(default=0, ge=0)


class SearchChanges(StrictModel):
    new: int = Field(default=0, ge=0)
    changed: int = Field(default=0, ge=0)
    reopened: int = Field(default=0, ge=0)
    closed: int = Field(default=0, ge=0)
    repeated_suppressed: int = Field(default=0, ge=0)
    closed_job_ids: tuple[str, ...] = ()


class SearchRunResult(StrictModel):
    """Search output plus evidence needed by field-trial evaluation."""

    matches: tuple[JobMatch, ...]
    diagnostics: SearchRunDiagnostics
    changes: SearchChanges = SearchChanges()


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


class SearchConfiguration(StrictModel):
    workspace: Workspace
    plan: SearchPlan
    sources: tuple[SourceSubscription, ...] = ()
    source_links: tuple[SourceLink, ...] = ()


class SuggestedPlan(StrictModel):
    """A search plan proposal derived from confirmed profile facts."""

    target_roles: tuple[str, ...]
    locations: tuple[str, ...] = ()
    salary_min_k: int | None = None
    salary_max_k: int | None = None
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    recruitment_track: RecruitmentTrack | None = None
    employment_type: EmploymentType | None = None
    exclusions: tuple[str, ...] = ()
    candidate_experience_years: int | None = Field(default=None, ge=0, le=80)
    confidence: Literal["low", "medium", "high"] = "low"
    requires_confirmation: tuple[str, ...] = ()
    reasoning: str = ""
    ready: bool = Field(
        default=True,
        description="False when no confirmed profile exists yet.",
    )


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


class ExportReceipt(StrictModel):
    path: str
    sha256: str
    record_counts: dict[str, int]
