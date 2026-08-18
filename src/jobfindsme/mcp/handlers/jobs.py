"""get_jobs / update_job_state handlers — job listing, details, tracking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult
from jobfindsme.mcp.responses import jobs_list_text


def get_jobs(core: Any, request: BaseModel) -> HandlerResult:
    """List job summaries, or return full details for one job_id."""
    values = request.model_dump()
    job_id = values.pop("job_id", None)
    if job_id:
        details = core.get_job_details(job_id=job_id)
        return None, details
    jobs = core.list_job_summaries(**values)
    next_offset = values["offset"] + len(jobs) if len(jobs) == values["limit"] else None
    structured = {
        "jobs": jobs,
        "count": len(jobs),
        "offset": values["offset"],
        "limit": values["limit"],
        "next_offset": next_offset,
    }
    return jobs_list_text(jobs), structured


def update_job_state(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    state = core.update_job_state(
        **values,
    )
    return None, state
