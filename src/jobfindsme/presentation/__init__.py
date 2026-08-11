"""Presentation — deterministic, evidence-grounded output rendering.

    search_result.py  — the five-section search contract (①-⑤) + source lines
    job_block.py      — per-job blocks: facts, match, signals, link, reason

Every claim MUST be backed by structured signals or job fields.
"""

from __future__ import annotations

from jobfindsme.presentation.job_block import format_job_list
from jobfindsme.presentation.search_result import (
    _short_error,
    _source_line_from_runs,
    format_search_empty,
    format_search_results,
)

__all__ = [
    "_short_error",
    "_source_line_from_runs",
    "format_job_list",
    "format_search_empty",
    "format_search_results",
]
