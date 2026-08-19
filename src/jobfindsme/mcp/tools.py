"""MCP tool handlers — one module per user-facing domain is overkill;
five tools share this file.

Each handler returns ``(text | None, structured)``: the optional human
text (search_jobs renders the five-section baseline here) and the
structured value that the registry validates against the tool schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.responses import build_search_output, jobs_list_text
from jobfindsme.mcp.schemas import SearchJobsInput
from jobfindsme.presentation import format_search_results
from jobfindsme.profiles.models import FactType

HandlerResult = tuple[str | None, dict[str, Any]]


def setup(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    page: dict[str, Any] = {}

    # ── Profile part ────────────────────────────────────────────────────
    if values.get("resume_path"):
        profile = core.import_resume(
            source_path=values["resume_path"],
            mode=values["mode"],
        )
        if values["auto_confirm"]:
            profile = core.confirm_profile(
                profile_id=profile.profile_id,
                accepted_fact_ids=[fact.fact_id for fact in profile.facts],
            )
            include_facts = False
        else:
            include_facts = True
        page.update(
            _profile_page(
                profile,
                offset=values["offset"],
                limit=values["limit"],
                include_facts=include_facts,
            )
        )
    # ── Search plan part ────────────────────────────────────────────────
    if values.get("target_role"):
        # Keep typed fields (sources is a tuple of DiscoverySource models —
        # model_dump would corrupt them into raw dicts).
        plan = core.configure_search(
            target_role=request.target_role,
            locations=request.locations,
            salary_min_k=request.salary_min_k,
            salary_max_k=request.salary_max_k,
            salary_policy=request.salary_policy,
            experience_min_years=request.experience_min_years,
            experience_max_years=request.experience_max_years,
            recruitment_track=request.recruitment_track,
            employment_type=request.employment_type,
            exclusions=request.exclusions,
            sources=request.sources,
        )
        page["plan"] = plan
    return None, page


def _profile_page(
    profile: Any,
    *,
    offset: int,
    limit: int,
    include_facts: bool = True,
) -> dict[str, Any]:
    facts = tuple(profile.facts)
    selected = facts[offset : offset + limit] if include_facts else ()
    counts = {
        fact_type.value: sum(fact.fact_type is fact_type for fact in facts)
        for fact_type in FactType
    }
    next_offset = offset + len(selected) if include_facts else 0
    return {
        "profile_id": profile.profile_id,
        "profile_status": getattr(profile, "status", "confirmed"),
        "parser_version": getattr(profile, "parser_version", None),
        "fact_counts": counts,
        "facts": selected,
        "next_offset": next_offset if next_offset < len(facts) else None,
        "total_facts": len(facts),
        "review_available": bool(facts),
    }


def search_jobs(core: Any, request: BaseModel) -> HandlerResult:
    assert isinstance(request, SearchJobsInput)
    result = core.search_jobs_with_diagnostics(
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
        jobs=jobs,
        count=len(jobs),
        changes=result.changes,
        diagnostics=result.diagnostics,
    )
    return text, structured


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


def delete_local_data(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    if values["action"] == "preview":
        result = core.preview_delete(
            scope=values["scope"],
        )
        return None, result.model_dump(mode="json", exclude={"workspace_id"})
    token = values["confirmation_token"]
    if not token:
        raise ValueError("confirmation_token is required for confirm")
    result = core.confirm_delete(
        scope=values["scope"],
        confirmation_token=token,
    )
    return None, result.model_dump(mode="json", exclude={"workspace_id"})


def build_handlers() -> dict[str, Any]:
    """Wire every tool name to its handler function."""
    return {
        "setup": setup,
        "search_jobs": search_jobs,
        "get_jobs": get_jobs,
        "update_job_state": update_job_state,
        "delete_local_data": delete_local_data,
    }
