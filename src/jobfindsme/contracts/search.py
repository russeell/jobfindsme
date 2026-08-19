"""Search contracts: plans, constraints, configuration, diagnostics."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from jobfindsme.contracts.models import (
    EmploymentType,
    RecruitmentTrack,
    SourceLink,
    SourceRunStats,
    SourceSubscription,
    StrictModel,
)
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

    def to_preferences(self) -> Preferences:
        return Preferences(
            name=self.name,
            target_role=self.target_roles[0],
            locations=self.locations,
            salary_min_k=self.salary_min_k,
            salary_max_k=self.salary_max_k,
            salary_policy=self.salary_policy,
            experience_min_years=self.experience_min_years,
            experience_max_years=self.experience_max_years,
            recruitment_track=self.recruitment_track,
            employment_type=self.employment_type,
            exclusions=self.exclusions,
        )


class Preferences(StrictModel):
    """The user's search conditions — one profile + one set of preferences.

    Public contract replaces the internal Workspace/SearchPlan concepts.
    `target_role` is the single role used for discovery — one product
    decision at a time, instead of a role × city × platform cartesian product.
    """

    name: str = Field(default="Default Search", min_length=1, max_length=120)
    target_role: str = Field(min_length=1, max_length=120)
    locations: tuple[str, ...] = ()
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    salary_policy: SalaryPolicy = SalaryPolicy.STRICT
    experience_min_years: int | None = Field(default=None, ge=0, le=80)
    experience_max_years: int | None = Field(default=None, ge=0, le=80)
    recruitment_track: RecruitmentTrack | None = None
    employment_type: EmploymentType | None = None
    exclusions: tuple[str, ...] = ()

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
    """Control how much remote discovery an interactive search performs.

    LIVE refreshes maintained sources concurrently and degrades to labeled
    cache on per-source failure.  CACHE performs no remote access.  FAST and
    FULL are compatibility aliases of LIVE (they always behaved identically).
    """

    LIVE = "live"
    FAST = "live"  # deprecated alias
    FULL = "live"  # deprecated alias
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


class SearchConfiguration(StrictModel):
    preferences: Preferences
    sources: tuple[SourceSubscription, ...] = ()
    source_links: tuple[SourceLink, ...] = ()


class SearchDiagnosticSummary(StrictModel):
    """Compact per-source status for structuredContent.

    Deliberately omits raw errors, timestamps, per-source discovered counts,
    and full SourceRunStats; job-level facts travel in `jobs` instead.
    """

    refresh_mode: SearchRefreshMode
    source_summary: str = Field(
        default="",
        description=(
            "Pre-formatted source line, for example "
            "'BOSS直聘 △ 缓存 · 猎聘 ✓ 84 · 智联招聘 ✓ 30 · 前程无忧 △ 缓存'"
        ),
    )
    total_discovered: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)


class ExportReceipt(StrictModel):
    path: str
    sha256: str
    record_counts: dict[str, int]


class SearchPresentationContext(StrictModel):
    """Bounded facts required to render one search consistently."""

    profile_used: bool = False
    skill_count: int = Field(default=0, ge=0)
    project_count: int = Field(default=0, ge=0)
    experience_count: int = Field(default=0, ge=0)
    education_count: int = Field(default=0, ge=0)
    highest_degree: str | None = None
    applied_filters: tuple[str, ...] = ()
    total_matched_count: int = Field(default=0, ge=0)
    cumulative_shown_count: int = Field(default=0, ge=0)
    closed_count: int = Field(default=0, ge=0)
