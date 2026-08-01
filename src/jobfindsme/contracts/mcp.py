"""MCP-wire contracts: adapter-facing outputs that cross the stdio boundary.

These are the structured shapes returned to the host Agent.  They are kept
deliberately minimal so the host model cannot reconstruct job listings from
structuredContent alone (see SearchDiagnosticSummary / SearchIntegrity).
"""

from __future__ import annotations

from pydantic import Field

from jobfindsme.contracts.base import StrictModel, Workspace
from jobfindsme.contracts.search import (
    SearchPlan,
    SearchRefreshMode,
)
from jobfindsme.contracts.source import SourceLink, SourceSubscription


class SearchConfiguration(StrictModel):
    workspace: Workspace
    plan: SearchPlan
    sources: tuple[SourceSubscription, ...] = ()
    source_links: tuple[SourceLink, ...] = ()


class SearchDiagnosticSummary(StrictModel):
    """Compact per-source status for structuredContent.

    Deliberately omits raw errors, timestamps, per-source discovered counts,
    and full SourceRunStats so the host model cannot reconstruct job listings
    from structuredContent alone.  Full diagnostics remain embedded in the
    human-facing final_text (section 2).
    """

    refresh_mode: SearchRefreshMode
    source_summary: str = Field(
        default="",
        description=(
            "Pre-formatted source line, for example "
            "'BOSS直聘 ✓(42) · 猎聘 ✗(Chrome未连接)'"
        ),
    )
    total_discovered: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)


class SearchIntegrity(StrictModel):
    """Evidence that final_text was not modified by the transport layer."""

    sha256: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 hex digest of final_text (UTF-8 encoded)",
    )


class ExportReceipt(StrictModel):
    path: str
    sha256: str
    record_counts: dict[str, int]
