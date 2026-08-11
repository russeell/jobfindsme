"""search_jobs handler — the core search workflow.

search_jobs renders the five-section contract text and the deliberately
minimal structuredContent.  The host MUST return content[0].text verbatim;
handlers never expose job arrays through structuredContent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult
from jobfindsme.mcp.responses import build_search_output
from jobfindsme.mcp.schemas import SearchJobsInput
from jobfindsme.presentation import format_search_results


def search_jobs(core: Any, request: BaseModel) -> HandlerResult:
    assert isinstance(request, SearchJobsInput)
    result = core.search_jobs_with_diagnostics(
        workspace_id=request.workspace_id,
        plan_id=request.plan_id,
        sources=request.sources,
        limit=request.limit,
        allow_browser_sources=request.allow_browser_sources,
        refresh_mode=request.refresh_mode,
        include_seen=request.include_seen,
        use_profile=request.use_profile,
    )
    matches = result.matches
    summaries = {
        item.job_id: item
        for item in core.list_job_summaries(
            workspace_id=request.workspace_id,
            job_ids=[match.job.job_id for match in matches],
            limit=request.limit,
        )
    }
    jobs = [
        {
            "job": summaries[match.job.job_id],
            "score": match.score,
            "evidence": match.evidence,
            "state": match.state,
            "first_seen_at": match.first_seen_at,
            "change_type": match.change_type,
        }
        for match in matches
    ]
    presentation = core.search_presentation_context(
        workspace_id=request.workspace_id,
        plan_id=request.plan_id,
        use_profile=request.use_profile,
    )
    text = format_search_results(
        jobs,
        result.changes,
        result.diagnostics,
        presentation,
    )
    structured = build_search_output(
        text=text,
        count=len(jobs),
        changes=result.changes,
        diagnostics=result.diagnostics,
    )
    return text, structured
