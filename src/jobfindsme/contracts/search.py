"""Search-side contracts: plans, constraints, run diagnostics.

SearchPlan is the internal model behind the user-facing "Search" concept
(我找什么).  SalaryPolicy controls how strict an explicit salary
constraint is.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from jobfindsme.contracts.base import StrictModel
from jobfindsme.contracts.job import EmploymentType, RecruitmentTrack
from jobfindsme.contracts.source import SourceRunStats
from jobfindsme.contracts.tracking import JobMatch


class SalaryPolicy(StrEnum):
    """How an explicit salary constraint treats jobs without salary data."""

    STRICT = "strict"
    INCLUDE_UNDISCLOSED = "include_undisclosed"


class SearchPlan(StrictModel):
    plan_id: str = Field(min_length=1, max_length=128)
    workspace_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    target_roles: tuple[str, ...] = Field(min_length=1)
    locations: tuple[str, ...] = ()
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    salary_policy: SalaryPolicy = SalaryPolicy.STRICT
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


class SearchRefreshMode(StrEnum):
    """Control how much remote discovery an interactive search performs."""

    FAST = "fast"
    FULL = "full"
    CACHE = "cache"


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
    undisclosed_salary_filtered_count: int = Field(default=0, ge=0)
    undisclosed_salary_included_count: int = Field(default=0, ge=0)


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
