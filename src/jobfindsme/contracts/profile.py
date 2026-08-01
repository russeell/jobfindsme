"""Profile-side contracts: resume-derived plan suggestions and presentation facts.

These types bridge the Profile concept (我是谁) to Search (我找什么):
SuggestedPlan proposes search constraints from confirmed resume facts,
SearchPresentationContext carries the bounded fact counts the Server
renders in section ① of a search result.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from jobfindsme.contracts.base import StrictModel
from jobfindsme.contracts.job import EmploymentType, RecruitmentTrack


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


class SearchPresentationContext(StrictModel):
    """Bounded facts required to render one search consistently."""

    profile_used: bool = False
    skill_count: int = Field(default=0, ge=0)
    project_count: int = Field(default=0, ge=0)
    experience_count: int = Field(default=0, ge=0)
    education_count: int = Field(default=0, ge=0)
    highest_degree: str | None = None
    applied_filters: tuple[str, ...] = ()
