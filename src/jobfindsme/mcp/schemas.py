from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jobfindsme.contracts import DiscoverySource, JobStateKind, StrictModel
from jobfindsme.profiles.models import ResumeImportMode


class SetupProfileInput(StrictModel):
    action: Literal["import", "confirm"] = "import"
    workspace_id: str
    resume_path: str | None = None
    mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE
    profile_id: str | None = None
    accepted_fact_ids: tuple[str, ...] = ()
    corrections: dict[str, str] = Field(default_factory=dict)

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
        return self


class SearchJobsInput(StrictModel):
    workspace_id: str
    plan_id: str
    sources: tuple[DiscoverySource, ...] = ()
    limit: int = Field(default=20, ge=1, le=100)


class GetJobsInput(StrictModel):
    workspace_id: str


class UpdateJobStateInput(StrictModel):
    workspace_id: str
    job_id: str
    state: JobStateKind
    note: str = Field(default="", max_length=1000)


class ConfigureMonitorInput(StrictModel):
    workspace_id: str
    plan_id: str
    enabled: bool
    interval_hours: int = Field(default=24, ge=1, le=168)
    notification_channel: str | None = None


class ExportLocalDataInput(StrictModel):
    workspace_id: str


class DeleteLocalDataInput(StrictModel):
    workspace_id: str
    scope: Literal["jobs", "profile", "workspace"]
    action: Literal["preview", "confirm"] = "preview"
    confirmation_token: str | None = None
