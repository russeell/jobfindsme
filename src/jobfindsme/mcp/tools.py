from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from jobfindsme.core import JobFindsMeCore
from jobfindsme.mcp.schemas import (
    ConfigureMonitorInput,
    DeleteLocalDataInput,
    ExportLocalDataInput,
    GetJobsInput,
    SearchJobsInput,
    SetupProfileInput,
    UpdateJobStateInput,
)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]

    def protocol_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(),
        }


TOOL_DEFINITIONS = (
    ToolDefinition(
        "setup_profile",
        "Parse a local resume without returning or storing its complete text.",
        SetupProfileInput,
    ),
    ToolDefinition(
        "search_jobs",
        "Discover from explicit sources, then match against a Search Plan.",
        SearchJobsInput,
    ),
    ToolDefinition(
        "get_jobs",
        "Return locally stored jobs and their source evidence.",
        GetJobsInput,
    ),
    ToolDefinition(
        "update_job_state",
        "Save, reject, or mark a job as applied.",
        UpdateJobStateInput,
    ),
    ToolDefinition(
        "configure_monitor",
        "Configure a local monitor; no run occurs without explicit enablement.",
        ConfigureMonitorInput,
    ),
    ToolDefinition(
        "export_local_data",
        "Export the local workspace without complete resume text.",
        ExportLocalDataInput,
    ),
    ToolDefinition(
        "delete_local_data",
        "Preview deletion, then confirm it with the short-lived Core token.",
        DeleteLocalDataInput,
    ),
)


class ToolRegistry:
    def __init__(self, core: JobFindsMeCore) -> None:
        self.core = core
        self._definitions = {item.name: item for item in TOOL_DEFINITIONS}

    def list_tools(self) -> list[dict[str, Any]]:
        return [item.protocol_schema() for item in TOOL_DEFINITIONS]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        definition = self._definitions.get(name)
        if definition is None:
            return _error(f"unknown tool: {name}")
        try:
            request = definition.input_model.model_validate(arguments)
            value = self._dispatch(name, request)
        except (ValidationError, ValueError, LookupError, PermissionError) as error:
            return _error(str(error))
        structured = _json_value(value)
        return {
            "content": [{"type": "text", "text": _compact_json(structured)}],
            "structuredContent": structured,
            "isError": False,
        }

    def _dispatch(self, name: str, request: BaseModel) -> Any:
        values = request.model_dump()
        if name == "setup_profile":
            if values["action"] == "confirm":
                return self.core.confirm_profile(
                    workspace_id=values["workspace_id"],
                    profile_id=values["profile_id"],
                    accepted_fact_ids=values["accepted_fact_ids"],
                    corrections=values["corrections"],
                )
            return self.core.import_resume(
                workspace_id=values["workspace_id"],
                source_path=values["resume_path"],
                mode=values["mode"],
            )
        if name == "search_jobs":
            assert isinstance(request, SearchJobsInput)
            return self.core.search_jobs(
                workspace_id=request.workspace_id,
                plan_id=request.plan_id,
                sources=request.sources,
                limit=request.limit,
            )
        if name == "get_jobs":
            return self.core.jobs.list(values["workspace_id"])
        if name == "update_job_state":
            return self.core.update_job_state(**values)
        if name == "configure_monitor":
            return self.core.configure_monitor(**values)
        if name == "export_local_data":
            return self.core.export_local_data(values["workspace_id"])
        if values["action"] == "preview":
            return self.core.preview_delete(
                workspace_id=values["workspace_id"],
                scope=values["scope"],
            )
        token = values["confirmation_token"]
        if not token:
            raise ValueError("confirmation_token is required for confirm")
        return self.core.confirm_delete(
            workspace_id=values["workspace_id"],
            scope=values["scope"],
            confirmation_token=token,
        )


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def _compact_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }
