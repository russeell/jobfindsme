"""get_jobs / get_job_details / update_job_state handlers — job tracking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult
from jobfindsme.mcp.responses import jobs_list_text


def get_jobs(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
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


def get_job_details(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    details = core.get_job_details(**values)
    return None, details


def update_job_state(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    workspace = core.context.resolve_workspace(values.pop("workspace_id"))
    state = core.update_job_state(
        workspace_id=workspace.workspace_id,
        **values,
    )
    return None, state
