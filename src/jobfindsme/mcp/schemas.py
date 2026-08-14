from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from jobfindsme.contracts import (
    DiscoverySource,
    EmploymentType,
    JobState,
    JobStateKind,
    JobSummary,
    RecruitmentTrack,
    SalaryPolicy,
    SearchChanges,
    SearchConfiguration,
    SearchDiagnosticSummary,
    SearchIntegrity,
    SearchRefreshMode,
    StrictModel,
    SuggestedPlan,
)
from jobfindsme.profiles.models import ProfileFact, ResumeImportMode


class SetupInput(StrictModel):
    """Initialize the local profile and search conditions in one call.

    Profile part (optional): pass resume_path to import and auto-confirm a
    resume. Pass profile_id + accepted_fact_ids to confirm after review.
    Search part (optional): pass target_roles to create/update the active
    search plan. Either part may be omitted — call setup again later.
    """

    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omit to use active context)",
    )

    # ── Profile ─────────────────────────────────────────────────────────
    resume_path: str | None = Field(
        default=None,
        description="Absolute path to resume file (import when provided)",
    )
    mode: ResumeImportMode = Field(
        default=ResumeImportMode.FORGET_SOURCE,
        description="forget-source (default) does not retain the original file",
    )
    auto_confirm: bool = Field(
        default=True,
        description="If true, auto-accepts all parsed facts so search can proceed",
    )
    profile_id: str | None = Field(
        default=None,
        description="Profile ID (required for review/confirm)",
    )
    accepted_fact_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Fact IDs to confirm (required for confirm)",
    )
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Map of fact_id to corrected value (optional)",
    )
    offset: int = Field(default=0, ge=0, description="Facts page offset")
    limit: int = Field(default=12, ge=1, le=50, description="Facts per page")

    # ── Search plan ─────────────────────────────────────────────────────
    plan_id: str | None = Field(
        default=None,
        description="Search Plan ID (omit to use active context)",
    )
    name: str = Field(
        default="Default Search",
        min_length=1,
        max_length=120,
        description="Human-readable label for this search plan",
    )
    target_roles: tuple[str, ...] = Field(
        default_factory=tuple,
        description=("Job titles to search, e.g. ['AI应用工程师', '大模型应用开发']"),
    )
    locations: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Cities, e.g. ['上海', '深圳']; empty = nationwide",
    )
    salary_min_k: int | None = Field(
        default=None, ge=0, le=1000, description="Min monthly salary in thousands"
    )
    salary_max_k: int | None = Field(
        default=None, ge=0, le=1000, description="Max monthly salary in thousands"
    )
    salary_policy: SalaryPolicy = Field(
        default=SalaryPolicy.STRICT,
        description=(
            "strict excludes jobs without salary when a salary filter is set; "
            "include_undisclosed keeps them with an explicit warning"
        ),
    )
    experience_min_years: int | None = Field(
        default=None, ge=0, le=80, description="Min years of experience"
    )
    experience_max_years: int | None = Field(
        default=None, ge=0, le=80, description="Max years of experience"
    )
    recruitment_track: RecruitmentTrack | None = Field(
        default=None,
        description="social (社招) or campus (校招); omit = both",
    )
    employment_type: EmploymentType | None = Field(
        default=None,
        description="full_time (正式), internship (实习), part_time (兼职); omit = all",
    )
    exclusions: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Keywords to exclude, e.g. ['外包', '996']",
    )
    sources: tuple[DiscoverySource, ...] | None = Field(
        default=None,
        description="Explicit sources; omit = maintained platforms auto-selected",
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.resume_path and self.profile_id:
            raise ValueError(
                "use either resume_path (import) or profile_id (review/confirm)"
            )
        if not self.resume_path and not self.profile_id and not self.target_roles:
            raise ValueError(
                "provide resume_path, profile_id, or target_roles — "
                "setup has nothing to do"
            )
        return self


class SearchJobsInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omit to use active context)",
    )
    plan_id: str | None = Field(
        default=None,
        description="Search Plan ID (omit to use active context)",
    )
    sources: tuple[DiscoverySource, ...] = Field(
        default_factory=tuple,
        description="Explicit source list; omit for auto-selected sources",
    )
    allow_browser_sources: bool = Field(
        default=True,
        description=(
            "Usually leave at the default (true). Set false only to skip "
            "browser-only BOSS直聘; maintained HTTP sources still run"
        ),
    )
    refresh_mode: SearchRefreshMode = Field(
        default=SearchRefreshMode.FAST,
        description=(
            "Usually leave at the default (fast): concurrently refresh the "
            "maintained sources, auto-degrading to labeled cache on failure. "
            "cache: no remote access. full: refresh all sources"
        ),
    )
    include_seen: bool = Field(
        default=True,
        description=(
            "Include previously-seen unchanged jobs for ordinary interactive "
            "searches. Set false only for explicitly incremental or scheduled "
            "radar requests."
        ),
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max jobs to return (1–100)",
    )
    use_profile: bool = Field(
        default=True,
        description=(
            "If false, skip the local profile entirely for this search — "
            "Section 1 will show '本次未使用简历，按用户明确条件匹配。' "
            "and no match percentages will appear.  "
            "The local profile is NOT deleted; it remains available for "
            "later searches.  Set to false when the user explicitly says "
            "they do not want to use a resume."
        ),
    )


class GetJobsInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omit to use active context)",
    )
    job_id: str | None = Field(
        default=None,
        description=(
            "One specific job ID — returns the full description and source "
            "provenance for that job."
        ),
    )
    job_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Filter by job IDs; empty = all jobs",
    )
    states: tuple[JobStateKind, ...] = Field(
        default_factory=tuple,
        description=(
            "Filter by state: discovered, saved, applied, rejected; empty = all states"
        ),
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
        description="Max jobs per page (1–50)",
    )


class UpdateJobStateInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omit to use active context)",
    )
    job_id: str = Field(
        description="Job ID to update",
    )
    state: JobStateKind = Field(
        description=(
            "saved (bookmark), applied (submitted), or rejected (not interested)"
        ),
    )
    note: str = Field(
        default="",
        max_length=1000,
        description="Optional note (max 1000 chars)",
    )


class DeleteLocalDataInput(StrictModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID (omit to use active context)",
    )
    scope: Literal["jobs", "profile", "workspace"] = Field(
        description=(
            "What to delete: jobs (all jobs), profile (resume data), "
            "or workspace (everything)"
        ),
    )
    action: Literal["preview", "confirm"] = Field(
        default="preview",
        description=(
            "preview: see what will be deleted (always call first); "
            "confirm: execute with token"
        ),
    )
    confirmation_token: str | None = Field(
        default=None,
        description="Token from preview response (required for confirm)",
    )


class SetupOutput(StrictModel):
    profile_id: str | None = None
    profile_status: str | None = None
    parser_version: str | None = None
    fact_counts: dict[str, int] = Field(default_factory=dict)
    facts: tuple[ProfileFact, ...] = ()
    next_offset: int | None = None
    total_facts: int = 0
    review_available: bool = False
    suggested_plan: SuggestedPlan | None = None
    plan: SearchConfiguration | None = None


class SearchJobsOutput(StrictModel):
    """search_jobs structuredContent — deliberately minimal.

    Contains ONLY the final rendered text, summary counts, and integrity
    evidence.  Does NOT expose the jobs array, JobSummary, MatchEvidence,
    JD excerpts, apply URLs, or full SearchRunDiagnostics — the host
    model MUST use get_jobs for structured job data
    and must never rebuild or rewrite the Server's final_text.
    """

    final_text: str = Field(
        description=(
            "Complete five-section human-facing result.  Byte-identical "
            "to content[0].text.  The host MUST return this verbatim."
        ),
    )
    count: int = Field(ge=0, description="Number of visible job results")
    changes: SearchChanges = Field(
        description="Change counts (new/changed/reopened/closed/repeated_suppressed)"
    )
    diagnostic_summary: SearchDiagnosticSummary = Field(
        description="Compact source status without job-level data"
    )
    integrity: SearchIntegrity = Field(
        description="SHA-256 of final_text for transport-integrity verification"
    )


class GetJobsOutput(StrictModel):
    jobs: tuple[JobSummary, ...]
    count: int
    offset: int
    limit: int
    next_offset: int | None = None


class DeleteLocalDataOutput(StrictModel):
    workspace_id: str
    scope: str
    record_counts: dict[str, int] | None = None
    confirmation_token: str | None = None
    expires_at: datetime | None = None
    deleted: bool | None = None
    deleted_at: datetime | None = None


MCP_OUTPUT_MODELS: dict[str, type[StrictModel]] = {
    "setup": SetupOutput,
    "search_jobs": SearchJobsOutput,
    # get_jobs returns either a JobSummary list or a JobDetails payload
    # depending on whether job_id is set — schema validation is skipped.
    "update_job_state": JobState,
    "delete_local_data": DeleteLocalDataOutput,
}
