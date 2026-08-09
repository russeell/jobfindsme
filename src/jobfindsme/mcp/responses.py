"""MCP response assembly: validation, error conversion, compact output.

ToolRegistry delegates every response-shaping decision here so handlers
stay focused on use-case work.  The search_jobs output is deliberately
minimal — the host model must never receive job arrays that could induce
it to rebuild the Server result.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError

from jobfindsme.presentation import format_job_list
from jobfindsme.presentation.diagnostics import _source_line_from_runs


def validate_output(model: type[Any], value: Any) -> dict[str, Any]:
    """Validate a handler value against its declared output schema.

    Raises ValidationError when the value does not match — the registry
    converts that into a tool error, never a protocol crash.
    """
    return model.model_validate(value).model_dump(mode="json")


def success_response(
    structured: dict[str, Any],
    *,
    text: str | None = None,
) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": text if text is not None else _compact_json(structured),
            }
        ],
        "structuredContent": structured,
        "isError": False,
    }


def error_response(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def jobs_list_text(jobs: list[Any]) -> str:
    """Render a get_jobs result as compact human-readable blocks."""
    return format_job_list(jobs)


def build_search_output(
    *,
    text: str,
    count: int,
    changes: Any,
    diagnostics: Any,
) -> dict[str, Any]:
    """Build the deliberately minimal structuredContent for search_jobs.

    The returned dict exposes ONLY final_text, count, changes, a compact
    diagnostic summary, and a SHA-256 integrity hash.  It deliberately
    OMITS the jobs array, JobSummary, MatchEvidence, JD excerpts, apply
    URLs, and full SearchRunDiagnostics — the host model cannot rebuild
    or rewrite the Server result from structuredContent alone.
    """
    # Normalise diagnostics to a plain dict (may be a Pydantic model).
    diag_dict: dict[str, Any] = (
        diagnostics.model_dump() if hasattr(diagnostics, "model_dump") else diagnostics
    )
    return {
        "final_text": text,
        "count": count,
        "changes": changes,
        "diagnostic_summary": {
            "refresh_mode": diag_dict.get("refresh_mode", "fast"),
            "source_summary": build_source_summary(diag_dict),
            "total_discovered": diag_dict.get("total_discovered", 0),
            "result_count": diag_dict.get("result_count", count),
        },
        "integrity": {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
    }


def build_source_summary(diagnostics: dict[str, Any]) -> str:
    """Build a compact source-status line from diagnostics.source_runs.

    Mirror of the section-2 source line in format_search_results, kept
    deliberately compact — no raw errors, no timestamps, no per-source
    discovered counts beyond the pre-formatted string.

    Chrome/CDP errors are sanitised to the single recovery message so the
    host model never sees raw commands, port numbers, or stack traces.
    """
    runs = diagnostics.get("source_runs", [])
    if runs:
        return _source_line_from_runs(runs)
    refresh_mode = diagnostics.get("refresh_mode", "fast")
    if refresh_mode == "cache":
        return "检索：本地缓存（本轮未刷新外部来源）"
    return "检索：本地缓存"


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _validate_or_error(
    model: type[Any] | None,
    value: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate *value* against *model*; return (structured, error_response).

    Returns (None, error) on schema mismatch so the registry can short-
    circuit without raising.
    """
    if model is None:
        return _json_value(value), None
    try:
        return validate_output(model, value), None
    except ValidationError:
        return None, error_response("tool output did not match its declared schema")
