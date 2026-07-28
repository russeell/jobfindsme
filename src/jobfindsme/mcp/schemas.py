from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jobfindsme.contracts import DiscoverySource, JobStateKind, StrictModel
from jobfindsme.profiles.models import ResumeImportMode


class SetupProfileInput(StrictModel):
    action: Literal["import", "review", "confirm"] = "import"
    workspace_id: str | None = None
    resume_path: str | None = None
    mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE
    auto_confirm: bool = True
    profile_id: str | None = None
    accepted_fact_ids: tuple[str, ...] = ()
    corrections: dict[str, str] = Field(default_factory=dict)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=12, ge=1, le=50)

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
    workspace_id: str | None = None
    plan_id: str | None = None
    sources: tuple[DiscoverySource, ...] = ()
    allow_browser_sources: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class ConfigureSearchInput(StrictModel):
    workspace_id: str | None = None
    plan_id: str | None = None
    name: str = Field(default="Default Search", min_length=1, max_length=120)
    target_roles: tuple[str, ...] = Field(min_length=1)
    locations: tuple[str, ...] = ()
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    experience_min_years: int | None = Field(default=None, ge=0, le=80)
    experience_max_years: int | None = Field(default=None, ge=0, le=80)
    exclusions: tuple[str, ...] = ()
    sources: tuple[DiscoverySource, ...] | None = None


class GetJobsInput(StrictModel):
    workspace_id: str | None = None
    job_ids: tuple[str, ...] = ()
    states: tuple[JobStateKind, ...] = ()
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=50)


class GetJobDetailsInput(StrictModel):
    workspace_id: str | None = None
    job_id: str


class UpdateJobStateInput(StrictModel):
    workspace_id: str | None = None
    job_id: str
    state: JobStateKind
    note: str = Field(default="", max_length=1000)


class ConfigureMonitorInput(StrictModel):
    workspace_id: str | None = None
    plan_id: str | None = None
    enabled: bool
    interval_hours: int = Field(default=24, ge=1, le=168)
    notification_channel: str | None = None


class ExportLocalDataInput(StrictModel):
    workspace_id: str | None = None


class DeleteLocalDataInput(StrictModel):
    workspace_id: str | None = None
    scope: Literal["jobs", "profile", "workspace"]
    action: Literal["preview", "confirm"] = "preview"
    confirmation_token: str | None = None
