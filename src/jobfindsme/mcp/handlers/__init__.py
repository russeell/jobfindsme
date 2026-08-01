"""MCP tool handlers — one module per user-facing domain.

Each handler owns its use-case orchestration and returns
``(text | None, structured)``: the optional human text (search_jobs
renders the five-section contract here) and the structured value that
the registry validates against the tool's output schema.

    profile.py  — setup_profile (我是谁)
    search.py   — configure_search / search_jobs (我找什么 / 找到了什么)
    jobs.py     — get_jobs / get_job_details / update_job_state (跟踪)
    privacy.py  — export_local_data / delete_local_data (数据主权)
"""

from __future__ import annotations

from typing import Any

HandlerResult = tuple[str | None, dict[str, Any]]


def build_handlers() -> dict[str, Any]:
    """Wire every tool name to its handler function.

    Imported lazily so registry.py stays free of use-case imports.
    """
    from jobfindsme.mcp.handlers.jobs import (
        get_job_details,
        get_jobs,
        update_job_state,
    )
    from jobfindsme.mcp.handlers.privacy import (
        delete_local_data,
        export_local_data,
    )
    from jobfindsme.mcp.handlers.profile import setup_profile
    from jobfindsme.mcp.handlers.search import configure_search, search_jobs

    return {
        "setup_profile": setup_profile,
        "configure_search": configure_search,
        "search_jobs": search_jobs,
        "get_jobs": get_jobs,
        "get_job_details": get_job_details,
        "update_job_state": update_job_state,
        "export_local_data": export_local_data,
        "delete_local_data": delete_local_data,
    }
