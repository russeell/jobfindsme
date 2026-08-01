"""Job-side contracts: postings, salary, summaries, and match evidence.

The four user-facing concepts map here as: Job (JobPosting / JobSummary)
and the evidence behind matching (MatchEvidence).  Salary lives with the
job it describes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from jobfindsme.contracts.base import StrictModel
from jobfindsme.contracts.source import (
    JobLiveness,
    JobSourceRecord,
    SourceEvidence,
)


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


class SalaryDetails(StrictModel):
    raw_text: str
    currency: str | None = None
    period: SalaryPeriod = SalaryPeriod.UNKNOWN
    min_amount: int | None = Field(default=None, ge=0)
    max_amount: int | None = Field(default=None, ge=0)
    months_per_year: int | None = Field(default=None, ge=1, le=24)
    normalized_annual_min: int | None = Field(default=None, ge=0)
    normalized_annual_max: int | None = Field(default=None, ge=0)


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
