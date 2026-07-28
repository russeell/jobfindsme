from __future__ import annotations

import ast
import json
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


def test_registry_exposes_product_level_tools(tmp_path) -> None:
    _, _, _, registry = make_registry(tmp_path)

    tools = registry.list_tools()

    assert [tool["name"] for tool in tools] == [
        "setup_profile",
        "configure_search",
        "search_jobs",
        "get_jobs",
        "get_job_details",
        "update_job_state",
        "configure_monitor",
        "export_local_data",
        "delete_local_data",
    ]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)


def test_first_use_does_not_require_workspace_or_plan_ids(tmp_path) -> None:
    core = JobFindsMeCore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")

    imported = registry.call(
        "setup_profile",
        {"action": "import", "resume_path": str(resume)},
    )
    configured = registry.call(
        "configure_search",
        {
            "target_roles": ["AI应用工程师"],
            "locations": ["上海"],
        },
    )
    searched = registry.call("search_jobs", {})

    assert imported["isError"] is False
    assert configured["isError"] is False
    assert configured["structuredContent"]["plan"]["target_roles"] == ["AI应用工程师"]
    assert searched["isError"] is False
    assert core.list_workspaces()


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


def test_setup_profile_supports_import_and_confirmation_in_one_tool(
    tmp_path,
) -> None:
    core, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG\n项目：本地求职引擎", encoding="utf-8")

    imported = registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
        },
    )
    profile = imported["structuredContent"]
    fact_ids = [fact["fact_id"] for fact in profile["facts"]]
    confirmed = registry.call(
        "setup_profile",
        {
            "action": "confirm",
            "workspace_id": workspace.workspace_id,
            "profile_id": profile["profile_id"],
            "accepted_fact_ids": fact_ids,
        },
    )

    assert confirmed["isError"] is False
    assert all(
        fact["status"] == "confirmed"
        for fact in confirmed["structuredContent"]["facts"]
    )


def test_job_tools_bound_context_and_require_explicit_details(tmp_path) -> None:
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "外部JD内容 " * 100,
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    summaries = registry.call("get_jobs", {"limit": 1})["structuredContent"]
    job_id = summaries[0]["job_id"]
    details = registry.call(
        "get_job_details",
        {"job_id": job_id},
    )["structuredContent"]

    assert len(summaries[0]["description_excerpt"]) <= 400
    assert "description" not in summaries[0]
    assert summaries[0]["untrusted_external_content"] is True
    assert details["job"]["description"].startswith("外部JD内容")
    assert details["untrusted_external_content"] is True


def test_mcp_export_returns_file_receipt_not_private_payload(tmp_path) -> None:
    core, _, _, registry = make_registry(tmp_path)

    result = registry.call("export_local_data", {})
    receipt = result["structuredContent"]

    assert set(receipt) == {"path", "sha256", "record_counts"}
    assert Path(receipt["path"]).exists()


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
