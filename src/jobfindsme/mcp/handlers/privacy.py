"""delete_local_data handler — two-phase local data deletion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from jobfindsme.mcp.handlers import HandlerResult


def delete_local_data(core: Any, request: BaseModel) -> HandlerResult:
    values = request.model_dump()
    if values["action"] == "preview":
        result = core.preview_delete(
            scope=values["scope"],
        )
        return None, result
    token = values["confirmation_token"]
    if not token:
        raise ValueError("confirmation_token is required for confirm")
    result = core.confirm_delete(
        scope=values["scope"],
        confirmation_token=token,
    )
    return None, result
