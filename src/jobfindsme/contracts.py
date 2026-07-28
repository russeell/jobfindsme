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


class SalaryPeriod(StrEnum):
    MONTH = "month"
    YEAR = "year"
    DAY = "day"
    HOUR = "hour"
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


class JobMatch(StrictModel):
    job: JobPosting
    score: float = Field(ge=0, le=1)
    evidence: MatchEvidence


class JobSummary(StrictModel):
    job_id: str
    title: str
    company: str
    locations: tuple[str, ...] = ()
    salary: SalaryDetails | None = None
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


class JobStateKind(StrEnum):
    DISCOVERED = "discovered"
    SAVED = "saved"
    APPLIED = "applied"
    REJECTED = "rejected"


class JobState(StrictModel):
    workspace_id: str
    job_id: str
    state: JobStateKind
    note: str = Field(default="", max_length=1000)
    updated_at: datetime


class DiscoverySourceKind(StrEnum):
    GREENHOUSE = "greenhouse"
    CAREER_URL = "career_url"
    JSON_FILE = "json_file"
    CSV_FILE = "csv_file"


class DiscoverySource(StrictModel):
    kind: DiscoverySourceKind
    source_name: str
    board_token: str | None = None
    url: str | None = None
    path: str | None = None
    robots_allowed: bool = False

    @model_validator(mode="after")
    def validate_kind_fields(self) -> Self:
        required = {
            DiscoverySourceKind.GREENHOUSE: self.board_token,
            DiscoverySourceKind.CAREER_URL: self.url,
            DiscoverySourceKind.JSON_FILE: self.path,
            DiscoverySourceKind.CSV_FILE: self.path,
        }[self.kind]
        if not required:
            raise ValueError(f"{self.kind} source is missing its locator")
        if self.kind is DiscoverySourceKind.CAREER_URL and not self.robots_allowed:
            raise ValueError("career_url requires robots_allowed=true")
        return self


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


class SearchConfiguration(StrictModel):
    workspace: Workspace
    plan: SearchPlan
    sources: tuple[SourceSubscription, ...] = ()


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
