from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from jobfindsme.contracts import StrictModel


class BehaviorCase(StrictModel):
    case_id: str
    prompt: str
    purpose: str


class BehaviorCaseSuite(StrictModel):
    suite_version: str
    cases: tuple[BehaviorCase, ...]


class BehaviorEvent(StrictModel):
    type: Literal["assistant", "tool_call", "tool_result", "file_read", "shell"]
    name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    path: str | None = None
    command: str | None = None


class BehaviorTranscript(StrictModel):
    case_id: str
    host: str
    events: tuple[BehaviorEvent, ...]


class BehaviorTranscriptSuite(StrictModel):
    suite_version: str
    skill_enabled: bool
    evidence_kind: Literal["contract_fixture", "live_agent"]
    transcripts: tuple[BehaviorTranscript, ...]


class BehaviorCaseResult(StrictModel):
    case_id: str
    host: str
    passed: bool
    failures: tuple[str, ...] = ()


class BehaviorReport(StrictModel):
    suite_version: str
    skill_enabled: bool
    evidence_kind: str
    hosts: tuple[str, ...]
    passed: int
    total: int
    gate_passed: bool
    failed_case_ids: tuple[str, ...]
    results: tuple[BehaviorCaseResult, ...]
