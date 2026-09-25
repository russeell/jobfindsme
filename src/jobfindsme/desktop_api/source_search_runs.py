"""Turn source collection results into a stable run outcome."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from jobfindsme.search.desktop import SourceExecutionResult


class BrowserCollection(Protocol):
    batches: int
    elapsed_seconds: float
    complete: bool
    cursor: str | None
    stop_reason: str


@dataclass(frozen=True)
class SourceRunOutcome:
    status: str
    pages_fetched: int
    elapsed_seconds: float
    coverage_status: str
    can_continue: bool
    next_cursor: str | None
    stop_reason: str
    error: str | None

    def response_fields(self) -> dict[str, object]:
        return asdict(self)


def source_run_outcome(
    result: SourceExecutionResult,
    *,
    collection: BrowserCollection | None,
    browser_error: str | None,
    normalization_errors: int,
    valid_count: int,
) -> SourceRunOutcome:
    pages = collection.batches if collection else result.pages_fetched
    elapsed = collection.elapsed_seconds if collection else result.elapsed_seconds
    if browser_error or normalization_errors:
        status = "partial" if valid_count else "failed"
        coverage = "partial" if valid_count else "failed"
        reason = browser_error.split(":", 1)[0] if browser_error else "invalid_records"
    elif collection:
        status = (
            "success" if collection.complete else "partial" if valid_count else "failed"
        )
        coverage = "complete" if collection.complete else status
        reason = collection.stop_reason
    else:
        status = "success"
        coverage = result.coverage_status
        reason = result.stop_reason
    cursor = collection.cursor if collection else result.next_cursor
    can_continue = bool(cursor) if collection else result.can_continue
    return SourceRunOutcome(
        status=status,
        pages_fetched=pages,
        elapsed_seconds=elapsed,
        coverage_status=coverage,
        can_continue=can_continue and not bool(browser_error),
        next_cursor=None if browser_error else cursor,
        stop_reason=reason,
        error=browser_error,
    )
