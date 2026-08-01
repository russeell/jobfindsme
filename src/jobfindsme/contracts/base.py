"""Shared model base and workspace identity."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base contract that rejects accidental or misspelled fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Workspace(StrictModel):
    workspace_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    created_at: datetime
