from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

from jobfindsme.core import jobfindsmecore
from jobfindsme.mcp import ToolRegistry
from jobfindsme.mcp.schemas import GetJobsOutput


def make_registry(tmp_path):
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
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
        "suggest_plan",
        "search_jobs",
        "get_jobs",
        "get_job_details",
        "update_job_state",
        "export_local_data",
        "delete_local_data",
    ]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
    assert all(tool["title"] for tool in tools)
    assert all(tool["outputSchema"]["type"] == "object" for tool in tools)
    assert all("annotations" in tool for tool in tools)
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["search_jobs"]["annotations"]["openWorldHint"] is True
    assert by_name["export_local_data"]["annotations"]["readOnlyHint"] is False
    assert by_name["delete_local_data"]["annotations"]["destructiveHint"] is True


def test_first_use_does_not_require_workspace_or_plan_ids(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
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
    # Search may return live results or be empty — both are valid
    assert isinstance(searched["structuredContent"]["jobs"], list)
    assert isinstance(searched["structuredContent"]["count"], int)
    assert core.list_workspaces()


def test_configure_search_persists_recruitment_and_employment_filters(
    tmp_path,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)

    result = registry.call(
        "configure_search",
        {
            "target_roles": ["AI应用工程师"],
            "locations": ["上海", "杭州"],
            "recruitment_track": "social",
            "employment_type": "full_time",
        },
    )

    plan = result["structuredContent"]["plan"]
    assert plan["recruitment_track"] == "social"
    assert plan["employment_type"] == "full_time"


def test_tool_validation_returns_actionable_execution_error(tmp_path) -> None:
    _, workspace, _, registry = make_registry(tmp_path)

    result = registry.call(
        "search_jobs",
        {"workspace_id": workspace.workspace_id, "plan_id": "missing", "extra": True},
    )

    assert result["isError"] is True
    assert "extra" in result["content"][0]["text"]


def test_output_schema_failure_is_a_tool_error_not_a_protocol_crash(tmp_path) -> None:
    _, _, _, registry = make_registry(tmp_path)
    registry._definitions["suggest_plan"] = replace(
        registry._definitions["suggest_plan"],
        output_model=GetJobsOutput,
    )

    result = registry.call("suggest_plan", {})

    assert result["isError"] is True
    assert result["content"][0]["text"] == (
        "tool output did not match its declared schema"
    )


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
            "auto_confirm": False,
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


def test_profile_import_is_paginated_instead_of_dumping_all_facts(tmp_path) -> None:
    _, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：" + "、".join(["Python", "RAG", "Agent", "MCP", "Docker", "Redis"]),
        encoding="utf-8",
    )

    imported = registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
            "auto_confirm": False,
            "limit": 2,
        },
    )["structuredContent"]
    reviewed = registry.call(
        "setup_profile",
        {
            "action": "review",
            "workspace_id": workspace.workspace_id,
            "profile_id": imported["profile_id"],
            "offset": imported["next_offset"],
            "limit": 2,
        },
    )["structuredContent"]

    assert len(imported["facts"]) == 2
    assert imported["total_facts"] >= 6
    assert reviewed["facts"]
    assert "fact_counts" in imported


def test_profile_import_auto_confirms_by_default_for_fast_first_use(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")

    result = registry.call(
        "setup_profile",
        {"action": "import", "resume_path": str(resume)},
    )

    profile = result["structuredContent"]
    assert result["isError"] is False
    assert profile["status"] == "confirmed"
    assert profile["facts"] == []
    assert profile["total_facts"] >= 2
    assert profile["fact_counts"]["skill"] >= 2
    assert profile["next_offset"] == 0
    assert profile["review_available"] is True
    assert profile["suggested_plan"]["ready"] is True
    assert "target_roles" in profile["suggested_plan"]["requires_confirmation"]


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
                        "description": "外部JD内容 " * 5000,
                        "recruitment_track": "social",
                        "employment_type": "full_time",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    page = registry.call("get_jobs", {"limit": 1})["structuredContent"]
    summaries = page["jobs"]
    job_id = summaries[0]["job_id"]
    details = registry.call(
        "get_job_details",
        {"job_id": job_id},
    )["structuredContent"]

    assert len(summaries[0]["description_excerpt"]) <= 400
    assert "description" not in summaries[0]
    assert summaries[0]["untrusted_external_content"] is True
    assert summaries[0]["recruitment_track"] == "social"
    assert summaries[0]["employment_type"] == "full_time"
    assert details["job"]["description"].startswith("外部JD内容")
    assert details["untrusted_external_content"] is True
    assert len(details["job"]["description"]) == 20_000
    assert details["description_truncated"] is True
    assert page["count"] == 1
    assert page["offset"] == 0
    assert page["limit"] == 1
    assert page["next_offset"] == 1
    assert (
        page["jobs"][0]["apply_url"]
        in registry.call("get_jobs", {"limit": 1})["content"][0]["text"]
    )


def test_job_list_text_has_stable_classification_and_link_format(tmp_path) -> None:
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "intern-1",
                        "title": "大模型应用工程师实习生",
                        "company": "示例科技",
                        "description": "校园招聘实习岗位",
                        "location": "上海",
                        "url": "https://example.com/jobs/intern-1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("get_jobs", {"limit": 1})
    text = result["content"][0]["text"]

    assert text == (
        "1. 大模型应用工程师实习生｜示例科技｜上海｜校招｜实习\n"
        "\n   投递链接：https://example.com/jobs/intern-1"
    )


def test_search_text_includes_score_reasons_and_warnings(tmp_path) -> None:
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "match-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent",
                        "location": "上海",
                        "url": "https://example.com/jobs/match-1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    assert [f"【{index}·" in text for index in range(1, 6)] == [True] * 5
    assert "简历解析：本次未使用简历" in text
    assert "过滤：角色(AI应用工程师) → 给出 1 个" in text
    assert "[新增] AI应用工程师" in text
    assert "匹配度：已通过角色、地点、薪资等可判定硬条件" in text
    assert "投递链接：https://example.com/jobs/match-1" in text
    assert "推荐理由：" in text
    assert "workspace" not in text.casefold()
    assert "plan_id" not in text.casefold()
    assert result["structuredContent"]["diagnostics"]["refresh_mode"] == "cache"
    assert result["structuredContent"]["jobs"][0]["job"]["job_id"]
    assert result["structuredContent"]["jobs"][0]["state"] == "discovered"
    assert result["structuredContent"]["jobs"][0]["change_type"] == "new"
    assert result["structuredContent"]["changes"]["new"] == 1
    # v0.4: evidence carries extracted_signals for Agent-side matching
    assert "extracted_signals" in result["structuredContent"]["jobs"][0]["evidence"]
    sig = result["structuredContent"]["jobs"][0]["evidence"]["extracted_signals"]
    assert isinstance(sig["required_skills"], list)


def test_search_explains_when_only_previously_shown_jobs_remain(tmp_path) -> None:
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            '[{"id":"seen","title":"AI应用工程师",'
            '"company":"示例科技","description":"Python RAG",'
            '"url":"https://example.com/jobs/seen"}]',
            source_name="fixture",
        ),
    )

    first = registry.call("search_jobs", {"refresh_mode": "cache"})
    second = registry.call("search_jobs", {"refresh_mode": "cache"})

    assert first["structuredContent"]["count"] == 1
    assert second["structuredContent"]["count"] == 0
    assert second["structuredContent"]["changes"]["repeated_suppressed"] == 1
    text = second["content"][0]["text"]
    assert all(f"【{index}·" in text for index in range(1, 6))
    assert "此前展示过" in text
    assert "重复岗位" not in text
    assert "之前没有做过有效抓取" not in text


def test_search_profile_section_returns_counts_without_resume_content(tmp_path) -> None:
    core, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python\n项目：内部项目ABC", encoding="utf-8")
    registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
        },
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    assert "【1·简历解析】" in text
    assert "技能 1 项" in text
    assert "项目 0 项" in text
    assert "Python" not in text
    assert "内部项目ABC" not in text
    assert result["structuredContent"]["presentation"]["profile_used"] is True


def test_search_distinguishes_source_failure_from_no_delta(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    registry.call(
        "configure_search",
        {
            "target_roles": ["AI应用工程师"],
            "sources": [
                {
                    "kind": "json_file",
                    "source_name": "损坏来源",
                    "path": str(tmp_path / "missing.json"),
                }
            ],
        },
    )

    result = registry.call("search_jobs", {"refresh_mode": "full"})

    assert result["isError"] is False
    assert result["structuredContent"]["count"] == 0
    assert "来源刷新失败" in result["content"][0]["text"]


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
