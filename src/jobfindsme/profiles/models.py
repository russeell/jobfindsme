from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from jobfindsme.contracts import StrictModel


class ResumeImportMode(StrEnum):
    REFERENCE = "reference"
    MANAGED = "managed"
    FORGET_SOURCE = "forget-source"


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class FactStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class FactType(StrEnum):
    SKILL = "skill"
    PROJECT = "project"
    EXPERIENCE = "experience"
    EDUCATION = "education"


class SourceDocument(StrictModel):
    document_id: str
    workspace_id: str
    file_name: str
    media_type: str
    content_hash: str
    import_mode: ResumeImportMode
    source_path: str | None = None
    managed_path: str | None = None
    parser_version: str
    created_at: datetime


class ProfileFact(StrictModel):
    fact_id: str
    fact_type: FactType
    value: str
    evidence_snippet: str = Field(min_length=1, max_length=500)
    evidence_start: int = Field(ge=0)
    evidence_end: int = Field(gt=0)
    status: FactStatus


class CandidateProfile(StrictModel):
    profile_id: str
    workspace_id: str
    document_id: str
    status: ProfileStatus
    parser_version: str
    facts: tuple[ProfileFact, ...] = ()
    created_at: datetime
    confirmed_at: datetime | None = None


class ProfileSummary(StrictModel):
    profile_id: str
    workspace_id: str
    facts: tuple[ProfileFact, ...]
