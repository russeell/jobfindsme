from __future__ import annotations

from typing import Literal

from pydantic import Field

from jobfindsme.contracts import JobStateKind, StrictModel
from jobfindsme.profiles.models import ResumeImportMode


class SetupProfileInput(StrictModel):
    workspace_id: str
    resume_path: str
    mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE


class SearchJobsInput(StrictModel):
    workspace_id: str
    plan_id: str
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
