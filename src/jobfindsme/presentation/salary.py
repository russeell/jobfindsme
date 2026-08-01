"""Salary-disclosure checks for presentation.

A source parser can retain numeric fields while the visible card says
"面议"; presentation must follow the source text in that conflict and
never claim an undisclosed salary is explicit.
"""

from __future__ import annotations

from jobfindsme.contracts import JobSummary


def _has_disclosed_salary(job: JobSummary) -> bool:
    """Return whether salary is both numeric and actually disclosed."""
    salary = job.salary
    if salary is None or not salary.raw_text.strip():
        return False
    normalized = salary.raw_text.casefold().replace(" ", "")
    undisclosed_markers = ("面议", "未公开", "未注明", "保密", "negotiable")
    if any(marker in normalized for marker in undisclosed_markers):
        return False
    return (
        salary.min_amount is not None
        or salary.max_amount is not None
        or salary.normalized_annual_min is not None
        or salary.normalized_annual_max is not None
    )
