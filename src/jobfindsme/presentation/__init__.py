"""Presentation package — rendering rules, split by concern.

Deterministic, evidence-grounded output shared by every adapter:

    search_result.py  — the five-section search contract (①-⑤)
    job_block.py      — per-job blocks: facts, match, signals, link, reason
    diagnostics.py    — source-status lines and safe error classification
    salary.py         — salary-disclosure checks

Rules: every claim MUST be backed by structured signals or job fields;
never infer company reputation, area desirability, industry outlook, or
benefit quality.
"""

from __future__ import annotations

from jobfindsme.presentation.diagnostics import _short_error
from jobfindsme.presentation.job_block import format_job_list
from jobfindsme.presentation.search_result import (
    format_search_empty,
    format_search_results,
)

__all__ = [
    "_short_error",
    "format_job_list",
    "format_search_empty",
    "format_search_results",
]
