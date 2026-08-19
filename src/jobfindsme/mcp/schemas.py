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
    MatchEvidence,
    RecruitmentTrack,
    SalaryPolicy,
    SearchChanges,
    SearchConfiguration,
    SearchDiagnosticSummary,
    SearchRefreshMode,
    StrictModel,
)
from jobfindsme.profiles.models import ProfileFact, ResumeImportMode


class _LegacyAwareInput(StrictModel):
    """Accept (and drop) pre-Step-1 workspace/plan IDs for client safety.

    The product no longer exposes Workspace/SearchPlan concepts; old clients
    that still send these fields must not crash.  Unknown fields other than
    these two remain rejected by StrictModel(extra="forbid").
    """

    @model_validator(mode="before")
    @classmethod
    def _strip_legacy_ids(cls, values: object) -> object:
        if isinstance(values, dict):
            values.pop("workspace_id", None)
            values.pop("plan_id", None)
        return values


class SetupInput(_LegacyAwareInput):
    """Initialize the local profile snapshot and search preferences in one call.

    Profile part (optional): pass resume_path to import and store a local
    snapshot.  Search part (optional): pass target_roles to create/update the
    local preferences.  Either part may be omitted — call setup again later.
    """

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
        description=(
            "If true (default), parsed facts are stored directly so the first "
            "search can proceed. Set false only for a facts review page."
        ),
    )
    offset: int = Field(default=0, ge=0, description="Facts page offset")
    limit: int = Field(default=12, ge=1, le=50, description="Facts per page")

    # ── Preferences ─────────────────────────────────────────────────────
    target_roles: tuple[str, ...] = Field(
        default_factory=tuple,
        description=("Target role, e.g. ['AI应用工程师']"),
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
        if not self.resume_path and not self.target_roles:
            raise ValueError(
                "provide resume_path or target_roles — setup has nothing to do"
            )
        return self


class SearchJobsInput(_LegacyAwareInput):
    @model_validator(mode="before")
    @classmethod
    def _normalize_refresh_mode(cls, values: object) -> object:
        """Map deprecated fast/full strings to the single live mode."""
        if isinstance(values, dict) and values.get("refresh_mode") in {"fast", "full"}:
            values["refresh_mode"] = "live"
        return values

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
        default=SearchRefreshMode.LIVE,
        description=(
            "Usually leave at the default (live): concurrently refresh the "
            "maintained sources, auto-degrading to labeled cache on failure. "
            "cache: no remote access."
        ),
    )
    include_seen: bool = Field(
        default=False,
        description=(
            "Default false: incremental radar behavior — only new, changed, "
            "reopened, or re-qualified jobs are returned. Set true when the "
            "user asks for the current full matching list even if some jobs "
            "were shown before."
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


class GetJobsInput(_LegacyAwareInput):
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


class UpdateJobStateInput(_LegacyAwareInput):
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


class DeleteLocalDataInput(_LegacyAwareInput):
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
    plan: SearchConfiguration | None = None


class SearchJobFact(StrictModel):
    """Bounded structured facts for one match (no full JD text)."""

    job: JobSummary
    score: float | None = Field(default=None, ge=0, le=1)
    state: str | None = None
    first_seen_at: datetime | None = None
    change_type: str | None = None
    evidence: MatchEvidence | None = None


class SearchJobsOutput(StrictModel):
    """search_jobs structuredContent — facts for the host to present.

    The Server decides facts, filtering, ranking, and evidence; the host
    Agent organizes the final user-facing expression.  `jobs` carries bounded
    structured facts (no full JD text), and `summary` is the Server's compact
    factual baseline which the Agent may adapt but must not contradict.
    """

    summary: str = Field(
        description=(
            "Compact factual baseline rendered by the Server (five sections). "
            "The host may reorganize wording but must keep every fact and "
            "apply URL from `jobs`."
        ),
    )
    count: int = Field(ge=0, description="Number of visible job results")
    jobs: tuple[SearchJobFact, ...] = Field(
        default_factory=tuple,
        description="Bounded structured facts per match (no full JD text)",
    )
    changes: SearchChanges = Field(
        description="Change counts (new/changed/reopened/closed/repeated_suppressed)"
    )
    diagnostic_summary: SearchDiagnosticSummary = Field(
        description="Compact source status without job-level data"
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
