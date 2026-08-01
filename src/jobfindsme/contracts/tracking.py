"""Tracking contracts: job state and incremental changes.

"Tracking" is the user-facing concept behind these types: what changed
compared to the last search, and what the user did with each job
(applied / saved / rejected).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from jobfindsme.contracts.base import StrictModel
from jobfindsme.contracts.job import JobPosting, MatchEvidence


class JobStateKind(StrEnum):
    DISCOVERED = "discovered"
    SAVED = "saved"
    APPLIED = "applied"
    REJECTED = "rejected"


class JobChangeType(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    REOPENED = "reopened"
    UNCHANGED = "unchanged"


class JobMatch(StrictModel):
    job: JobPosting
    score: float = Field(ge=0, le=1)
    evidence: MatchEvidence
    state: JobStateKind = JobStateKind.DISCOVERED
    first_seen_at: datetime | None = None
    change_type: JobChangeType | None = None


class JobState(StrictModel):
    workspace_id: str
    job_id: str
    state: JobStateKind
    note: str = Field(default="", max_length=1000)
    updated_at: datetime
