from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from evaluation.agent_behavior.models import (
    BehaviorCaseResult,
    BehaviorCaseSuite,
    BehaviorEvent,
    BehaviorReport,
    BehaviorTranscript,
    BehaviorTranscriptSuite,
)

_SECTIONS = tuple(f"【{index}·" for index in range(1, 6))
_APPLY_URL = re.compile(r"投递链接：https?://\S+")
_BARE_URL = re.compile(r"https?://\S+")


def _load(path: str | Path, model: type):
    return model.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _events(transcript: BehaviorTranscript, kind: str) -> list[BehaviorEvent]:
    return [event for event in transcript.events if event.type == kind]


def _tool_calls(transcript: BehaviorTranscript) -> list[BehaviorEvent]:
    return _events(transcript, "tool_call")


def _last_assistant(transcript: BehaviorTranscript) -> str:
    messages = _events(transcript, "assistant")
    return messages[-1].content if messages else ""


def _tool_result(transcript: BehaviorTranscript, name: str) -> str:
    results = [
        event.content
        for event in _events(transcript, "tool_result")
        if event.name == name
    ]
    return results[-1] if results else ""


def _tool_call(transcript: BehaviorTranscript, name: str) -> BehaviorEvent | None:
    return next(
        (event for event in _tool_calls(transcript) if event.name == name),
        None,
    )


def _tool_names(transcript: BehaviorTranscript) -> list[str]:
    return [event.name or "" for event in _tool_calls(transcript)]


def _require_factual_search_output(transcript: BehaviorTranscript) -> list[str]:
    """The assistant answer must be grounded in the tool result: every apply
    URL from the Server must survive into the final user-facing answer, and
    the answer must not be an empty echo of the request."""
    output = _tool_result(transcript, "search_jobs")
    if not output:
        return ["missing search_jobs tool result"]
    last = _last_assistant(transcript)
    if not last:
        return ["assistant gave no final answer after search_jobs"]
    server_urls = _BARE_URL.findall(output)
    if not server_urls:
        return ["search_jobs result contained no apply URLs"]
    missing = [url for url in server_urls if url not in last]
    if missing:
        return [f"apply URLs were dropped or rewritten: {missing[:2]}"]
    return []


def _find_jobs_with_resume(transcript: BehaviorTranscript) -> list[str]:
    failures: list[str] = []
    names = _tool_names(transcript)
    required = ["setup", "search_jobs"]
    positions = [names.index(name) for name in required if name in names]
    if len(positions) != len(required) or positions != sorted(positions):
        failures.append("expected setup -> search_jobs")
    setup = _tool_call(transcript, "setup")
    if setup is None or setup.arguments.get("resume_path") != "/tmp/resume.pdf":
        failures.append("resume path was not passed directly to setup")
    failures.extend(_require_factual_search_output(transcript))
    return failures


def _preserve_five_sections_and_links(transcript: BehaviorTranscript) -> list[str]:
    failures = _require_factual_search_output(transcript)
    output = _last_assistant(transcript)
    if _APPLY_URL.search(output) is None:
        failures.append("bare apply URL was not preserved")
    if "|---" in output:
        failures.append("server output was rebuilt as a table")
    return failures


def _explain_source_degradation(transcript: BehaviorTranscript) -> list[str]:
    failures = _require_factual_search_output(transcript)
    output = _last_assistant(transcript)
    if "来源说明" not in output:
        failures.append("source degradation was not explained")
    if "对我说" not in output:
        failures.append("recovery was not expressed as a chat action")
    if "Chrome未连接" not in output and "缓存" not in output:
        failures.append("degraded source state was hidden")
    return failures


def _mark_job_applied(transcript: BehaviorTranscript) -> list[str]:
    call = _tool_call(transcript, "update_job_state")
    if call is None:
        return ["update_job_state was not called"]
    failures = []
    if call.arguments.get("job_id") != "job-2":
        failures.append("wrong job was updated")
    if call.arguments.get("state") != "applied":
        failures.append("job state was not set to applied")
    return failures


def _incremental_search(transcript: BehaviorTranscript) -> list[str]:
    searches = [
        event for event in _tool_calls(transcript) if event.name == "search_jobs"
    ]
    if len(searches) != 1:
        return ["incremental request must make exactly one search_jobs call"]
    failures = []
    if searches[0].arguments.get("include_seen") is not False:
        failures.append("incremental search did not suppress previously shown jobs")
    if searches[0].arguments.get("refresh_mode", "fast") == "full":
        failures.append("incremental search retried with a full refresh")
    return failures


def _protect_resume_context(transcript: BehaviorTranscript) -> list[str]:
    failures = []
    reads = _events(transcript, "file_read")
    if any((event.path or "").endswith("resume.pdf") for event in reads):
        failures.append("the complete resume was read into Agent context")
    setup = _tool_call(transcript, "setup")
    if setup is None or setup.arguments.get("resume_path") != "/tmp/resume.pdf":
        failures.append("resume path was not delegated to local Core")
    serialized = json.dumps(
        [event.arguments for event in _tool_calls(transcript)], ensure_ascii=False
    )
    if "完整简历正文" in serialized:
        failures.append("resume content leaked into tool arguments")
    return failures


_CHECKS: dict[str, Callable[[BehaviorTranscript], list[str]]] = {
    "find_jobs_with_resume": _find_jobs_with_resume,
    "preserve_five_sections_and_links": _preserve_five_sections_and_links,
    "explain_source_degradation": _explain_source_degradation,
    "mark_job_applied": _mark_job_applied,
    "incremental_search": _incremental_search,
    "protect_resume_context": _protect_resume_context,
}


def evaluate_behavior_suite(
    cases_path: str | Path,
    transcripts_path: str | Path,
) -> BehaviorReport:
    cases = _load(cases_path, BehaviorCaseSuite)
    transcripts = _load(transcripts_path, BehaviorTranscriptSuite)
    if cases.suite_version != transcripts.suite_version:
        raise ValueError("behavior case and transcript suite versions differ")
    case_ids = {case.case_id for case in cases.cases}
    unknown = {item.case_id for item in transcripts.transcripts} - case_ids
    missing = case_ids - {item.case_id for item in transcripts.transcripts}
    if unknown or missing:
        raise ValueError(
            f"behavior transcript coverage mismatch: missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )

    results = []
    for transcript in transcripts.transcripts:
        check = _CHECKS.get(transcript.case_id)
        if check is None:
            raise ValueError(f"no evaluator for behavior case: {transcript.case_id}")
        failures = tuple(check(transcript))
        results.append(
            BehaviorCaseResult(
                case_id=transcript.case_id,
                host=transcript.host,
                passed=not failures,
                failures=failures,
            )
        )
    failed = tuple(sorted({result.case_id for result in results if not result.passed}))
    return BehaviorReport(
        suite_version=cases.suite_version,
        skill_enabled=transcripts.skill_enabled,
        evidence_kind=transcripts.evidence_kind,
        hosts=tuple(sorted({item.host for item in transcripts.transcripts})),
        passed=sum(result.passed for result in results),
        total=len(results),
        gate_passed=not failed,
        failed_case_ids=failed,
        results=tuple(results),
    )
