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


class JobMatch(StrictModel):
    job: JobPosting
    score: float = Field(ge=0, le=1)
    evidence: MatchEvidence


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
