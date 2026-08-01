"""export_local_data / delete_local_data handlers — privacy and portability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult


def export_local_data(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    receipt = core.export_local_file(values["workspace_id"])
    return None, receipt


def delete_local_data(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    workspace = core.context.resolve_workspace(values["workspace_id"])
    if values["action"] == "preview":
        result = core.preview_delete(
            workspace_id=workspace.workspace_id,
            scope=values["scope"],
        )
        return None, result
    token = values["confirmation_token"]
    if not token:
        raise ValueError("confirmation_token is required for confirm")
    result = core.confirm_delete(
        workspace_id=workspace.workspace_id,
        scope=values["scope"],
        confirmation_token=token,
    )
    return None, result
