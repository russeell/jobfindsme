from __future__ import annotations

import ast
from pathlib import Path

from jobfindsme.core import JobFindsMeCore
from jobfindsme.mcp import ToolRegistry


def make_registry(tmp_path):
    core = JobFindsMeCore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("MCP")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )
    return core, workspace, plan, ToolRegistry(core)


def test_registry_exposes_exactly_seven_high_level_tools(tmp_path) -> None:
    _, _, _, registry = make_registry(tmp_path)

    tools = registry.list_tools()

    assert [tool["name"] for tool in tools] == [
        "setup_profile",
        "search_jobs",
        "get_jobs",
        "update_job_state",
        "configure_monitor",
        "export_local_data",
        "delete_local_data",
    ]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)


def test_tool_validation_returns_actionable_execution_error(tmp_path) -> None:
    _, workspace, _, registry = make_registry(tmp_path)

    result = registry.call(
        "search_jobs",
        {"workspace_id": workspace.workspace_id, "plan_id": "missing", "extra": True},
    )

    assert result["isError"] is True
    assert "extra" in result["content"][0]["text"]


def test_delete_tool_cannot_bypass_core_two_phase_protocol(tmp_path) -> None:
    core, workspace, _, registry = make_registry(tmp_path)

    bypass = registry.call(
        "delete_local_data",
        {
            "workspace_id": workspace.workspace_id,
            "scope": "workspace",
            "action": "confirm",
            "confirmation_token": "invented",
        },
    )
    assert bypass["isError"] is True
    assert core.list_workspaces() == [workspace]

    preview = registry.call(
        "delete_local_data",
        {
            "workspace_id": workspace.workspace_id,
            "scope": "workspace",
            "action": "preview",
        },
    )
    token = preview["structuredContent"]["confirmation_token"]
    confirmed = registry.call(
        "delete_local_data",
        {
            "workspace_id": workspace.workspace_id,
            "scope": "workspace",
            "action": "confirm",
            "confirmation_token": token,
        },
    )

    assert confirmed["isError"] is False
    assert core.list_workspaces() == []


def test_monitor_configuration_is_persisted_by_core(tmp_path) -> None:
    core, workspace, plan, registry = make_registry(tmp_path)

    result = registry.call(
        "configure_monitor",
        {
            "workspace_id": workspace.workspace_id,
            "plan_id": plan.plan_id,
            "enabled": True,
            "interval_hours": 12,
            "notification_channel": "feishu",
        },
    )

    assert result["structuredContent"]["enabled"] is True
    with core.database.connect() as connection:
        row = connection.execute("SELECT * FROM monitor_configs").fetchone()
    assert row["interval_hours"] == 12


def test_mcp_layer_contains_no_matching_or_persistence_imports() -> None:
    root = Path(__file__).parents[2] / "src" / "jobfindsme" / "mcp"
    forbidden = {"sqlite3", "matching", "importing", "storage"}

    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {
            node.module.split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        modules.update(
            alias.name.split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert modules.isdisjoint(forbidden), path
