from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jobfindsme.contracts import (
    DiscoverySource,
    EmploymentType,
    JobStateKind,
    RecruitmentTrack,
    SearchRefreshMode,
    StrictModel,
)
from jobfindsme.profiles.models import ResumeImportMode


class SetupProfileInput(StrictModel):
    action: Literal["import", "review", "confirm"] = Field(
        default="import",
        description="import: parse resume at resume_path; review: paginate facts; confirm: accept facts by ID",
    )
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    resume_path: str | None = Field(
        default=None,
        description="Absolute path to the local resume file (required for import action)",
    )
    mode: ResumeImportMode = Field(
        default=ResumeImportMode.FORGET_SOURCE,
        description="How to handle the source file: forget-source (default) does not retain the original",
    )
    auto_confirm: bool = Field(
        default=True,
        description="When true, auto-accepts all parsed facts so search can proceed immediately",
    )
    profile_id: str | None = Field(
        default=None,
        description="Profile ID (required for review and confirm actions)",
    )
    accepted_fact_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="List of fact IDs the user confirms (required for confirm action)",
    )
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Map of fact_id to corrected value (optional)",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset for review action (0-based)",
    )
    limit: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Maximum facts per review page (1-50)",
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action == "import" and not self.resume_path:
            raise ValueError("resume_path is required for import")
        if self.action == "confirm" and (
            not self.profile_id or not self.accepted_fact_ids
        ):
            raise ValueError(
                "profile_id and accepted_fact_ids are required for confirm"
            )
        if self.action == "review" and not self.profile_id:
            raise ValueError("profile_id is required for review")
        return self


class SearchJobsInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    plan_id: str | None = Field(
        default=None,
        description="Search Plan ID (omitted auto-resolves to active context)",
    )
    sources: tuple[DiscoverySource, ...] = Field(
        default_factory=tuple,
        description="Explicit source list; omit to use auto-selected maintained sources",
    )
    allow_browser_sources: bool = Field(
        default=True,
        description="When false, skip BOSS直聘 (requires local Chrome); 猎聘 still runs via HTTP",
    )
    refresh_mode: SearchRefreshMode = Field(
        default=SearchRefreshMode.FAST,
        description=(
            "fast: refresh primary live source, reuse caches for others. "
            "cache: no remote access, local DB only. "
            "full: refresh all sources in parallel"
        ),
    )
    include_seen: bool = Field(
        default=False,
        description="When true, include previously-seen unchanged jobs; default suppresses them",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum jobs to return (1-100)",
    )


class ConfigureSearchInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    plan_id: str | None = Field(
        default=None,
        description="Search Plan ID (omitted auto-resolves to active context)",
    )
    name: str = Field(
        default="Default Search",
        min_length=1,
        max_length=120,
        description="Human-readable label for this search plan",
    )
    target_roles: tuple[str, ...] = Field(
        min_length=1,
        description="Job titles to search for, e.g. ['AI应用工程师', '大模型应用开发'] (required)",
    )
    locations: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Cities to search, e.g. ['上海', '深圳', '杭州']; empty = nationwide",
    )
    salary_min_k: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Minimum monthly salary in thousands (K), e.g. 20 = 20K/月",
    )
    salary_max_k: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Maximum monthly salary in thousands (K), e.g. 50 = 50K/月",
    )
    experience_min_years: int | None = Field(
        default=None,
        ge=0,
        le=80,
        description="Minimum years of experience required by the job",
    )
    experience_max_years: int | None = Field(
        default=None,
        ge=0,
        le=80,
        description="Maximum years of experience you are willing to consider",
    )
    recruitment_track: RecruitmentTrack | None = Field(
        default=None,
        description="social (社招) or campus (校招); omit to include both",
    )
    employment_type: EmploymentType | None = Field(
        default=None,
        description="full_time (正式), internship (实习), or part_time (兼职); omit to include all",
    )
    exclusions: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Keywords to exclude from results, e.g. ['外包', '996']",
    )
    sources: tuple[DiscoverySource, ...] | None = Field(
        default=None,
        description="Explicit source list; omit to auto-select BOSS直聘 + 猎聘",
    )


class SuggestPlanInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )


class GetJobsInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    job_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Filter by specific job IDs; empty = return all",
    )
    states: tuple[JobStateKind, ...] = Field(
        default_factory=tuple,
        description="Filter by state: discovered, saved, applied, or rejected; empty = all states",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset (0-based)",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum jobs per page (1-50)",
    )


class GetJobDetailsInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    job_id: str = Field(
        description="The job ID from a get_jobs or search_jobs result",
    )


class UpdateJobStateInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    job_id: str = Field(
        description="The job ID to update",
    )
    state: JobStateKind = Field(
        description="saved (bookmark), applied (submitted application), or rejected (not interested)",
    )
    note: str = Field(
        default="",
        max_length=1000,
        description="Optional note about this state change (max 1000 chars)",
    )


class ConfigureMonitorInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    plan_id: str | None = Field(
        default=None,
        description="Search Plan ID (omitted auto-resolves to active context)",
    )
    enabled: bool = Field(
        description="true to start periodic background search; false to stop",
    )
    interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between automatic search runs (1-168, default 24 = daily)",
    )
    notification_channel: str | None = Field(
        default=None,
        description="Optional notification channel, e.g. 'feishu'",
    )


class ExportLocalDataInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )


class DeleteLocalDataInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omitted auto-resolves to active context)",
    )
    scope: Literal["jobs", "profile", "workspace"] = Field(
        description="What to delete: 'jobs' (all jobs), 'profile' (resume data), or 'workspace' (everything)",
    )
    action: Literal["preview", "confirm"] = Field(
        default="preview",
        description="preview: see what will be deleted (always call first); confirm: execute deletion with token",
    )
    confirmation_token: str | None = Field(
        default=None,
        description="Short-lived token from the preview response (required for confirm action)",
    )
