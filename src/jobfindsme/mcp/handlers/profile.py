"""setup_profile handler — import / review / confirm a local resume.

The response always carries ``suggested_plan`` (profile-derived search
constraints), so the Agent can jump straight to configure_search without
a separate tool call.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult
from jobfindsme.profiles.models import FactType


def setup_profile(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    if values["action"] == "confirm":
        profile = core.confirm_profile(
            workspace_id=values["workspace_id"],
            profile_id=values["profile_id"],
            accepted_fact_ids=values["accepted_fact_ids"],
            corrections=values["corrections"],
        )
        page = _profile_page(
            profile,
            offset=values["offset"],
            limit=values["limit"],
        )
        page["suggested_plan"] = core.suggest_plan(workspace_id=values["workspace_id"])
        return None, page
    if values["action"] == "review":
        profile = core.review_profile(
            workspace_id=values["workspace_id"],
            profile_id=values["profile_id"],
        )
    else:
        profile = core.import_resume(
            workspace_id=values["workspace_id"],
            source_path=values["resume_path"],
            mode=values["mode"],
        )
        if values["auto_confirm"]:
            profile = core.confirm_profile(
                workspace_id=values["workspace_id"],
                profile_id=profile.profile_id,
                accepted_fact_ids=[fact.fact_id for fact in profile.facts],
            )
    page = _profile_page(
        profile,
        offset=values["offset"],
        limit=values["limit"],
        include_facts=not (values["action"] == "import" and values["auto_confirm"]),
    )
    if values["auto_confirm"] and values["action"] == "import":
        page["suggested_plan"] = core.suggest_plan(workspace_id=values["workspace_id"])
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
        "status": getattr(profile, "status", "confirmed"),
        "parser_version": getattr(profile, "parser_version", None),
        "fact_counts": counts,
        "facts": selected,
        "next_offset": next_offset if next_offset < len(facts) else None,
        "total_facts": len(facts),
        "review_available": bool(facts),
    }
