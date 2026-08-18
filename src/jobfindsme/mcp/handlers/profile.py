"""setup handler — initialize profile and search conditions in one call.

Profile part: import / review / confirm a local resume (auto-confirm by
default).  Search part: create or update the active search plan.  Either
part may be omitted — call setup again later to extend.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult
from jobfindsme.profiles.models import FactType


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
    elif values.get("profile_id"):
        if values.get("accepted_fact_ids"):
            profile = core.confirm_profile(
                profile_id=values["profile_id"],
                accepted_fact_ids=values["accepted_fact_ids"],
                corrections=values["corrections"],
            )
        else:
            profile = core.review_profile(
                profile_id=values["profile_id"],
            )
        page.update(
            _profile_page(
                profile,
                offset=values["offset"],
                limit=values["limit"],
            )
        )
    # ── Search plan part ────────────────────────────────────────────────
    if values.get("target_roles"):
        # Keep typed fields (sources is a tuple of DiscoverySource models —
        # model_dump would corrupt them into raw dicts).
        plan = core.configure_search(
            target_roles=request.target_roles,
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
