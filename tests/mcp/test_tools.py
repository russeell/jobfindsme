from __future__ import annotations

import ast
import json
import re
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
    assert isinstance(searched["structuredContent"]["final_text"], str)
    assert isinstance(searched["structuredContent"]["count"], int)
    assert "integrity" in searched["structuredContent"]
    assert "diagnostic_summary" in searched["structuredContent"]
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
    registry._definitions["configure_search"] = replace(
        registry._definitions["configure_search"],
        output_model=GetJobsOutput,
    )

    result = registry.call(
        "configure_search",
        {"target_roles": ["AI应用工程师"]},
    )

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
    assert result["structuredContent"]["diagnostic_summary"]["refresh_mode"] == "cache"
    assert result["structuredContent"]["count"] == 1
    assert result["structuredContent"]["changes"]["new"] == 1
    # v0.7.2: structuredContent no longer exposes jobs/evidence — text is the contract
    assert "jobs" not in result["structuredContent"]
    assert "evidence" not in result["structuredContent"]
    assert "final_text" in result["structuredContent"]
    assert "integrity" in result["structuredContent"]


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
    second = registry.call(
        "search_jobs", {"refresh_mode": "cache", "include_seen": False}
    )

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
    # v0.7.2: profile_used is now only in final_text section 1, not structuredContent
    assert "简历解析：技能" in text


def test_search_sparse_jd_with_profile_hides_signal_percentage(tmp_path) -> None:
    """Sparse JD text must not render a misleading low percentage."""
    core, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python", encoding="utf-8")
    registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
        },
    )
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "sparse",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "",
                        "location": "上海",
                        "url": "https://example.com/jobs/sparse",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    assert "匹配度：已通过角色、地点、薪资等可判定硬条件" in text
    assert "JD 信息有限，未给出信号百分比" in text
    assert not re.search(r"匹配度：\d+%", text)


def test_search_reason_lists_matched_and_missing_skills(tmp_path) -> None:
    """推荐理由 must name resume skills that hit and JD skills that are missing."""
    core, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")
    registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
        },
    )
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "rich",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Kubernetes 3-5年 25-40K",
                        "location": "上海",
                        "url": "https://example.com/jobs/rich",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    assert "匹配度：43%（信号匹配，非录用概率）" in text
    assert "简历技能命中：Python、RAG" in text
    assert "岗位要求但简历未体现：Kubernetes" in text


def test_search_changes_section_has_four_levels(tmp_path) -> None:
    """⑤ 说明 must always render the four change levels as fixed bullets."""
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
    first_text = first["content"][0]["text"]
    assert "- 🆕 新增：1 条" in first_text
    assert "- ✏️ 变更：0 条" in first_text
    assert "- 🔄 重开：0 条" in first_text
    assert "- ⛔ 关闭：0 条" in first_text
    assert "重复抑制" not in first_text

    second = registry.call(
        "search_jobs", {"refresh_mode": "cache", "include_seen": False}
    )
    second_text = second["content"][0]["text"]
    assert "- 🆕 新增：0 条" in second_text
    assert "- 🔁 重复抑制（此前展示且未变化）：1 条" in second_text


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


# ── Regression: block integrity ──────────────────────────────────────────


def test_21_job_blocks_all_complete_with_consecutive_numbering(tmp_path) -> None:
    """Each job block must be atomically complete — fact line, match degree,
    signal line, bare URL, and evidence-grounded recommendation with
    consecutive numbering 1..21.

    Splits the output into per-block slices by adjacent numbering and
    asserts each individually, not just a global string search.
    """
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    records = [
        {
            "id": f"job-{i}",
            "title": "AI应用工程师",
            "company": f"示例科技{i}",
            "description": "Python RAG Agent 大模型 3-5年 25-40K",
            "location": "上海",
            "url": f"https://example.com/jobs/{i}",
        }
        for i in range(1, 22)  # 21 jobs
    ]
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(json.dumps(records, ensure_ascii=False), source_name="企业官网"),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache", "limit": 21})
    text = result["content"][0]["text"]

    # Five sections present
    for section_idx in range(1, 6):
        assert f"【{section_idx}·" in text, f"Missing section {section_idx}"

    assert result["structuredContent"]["count"] == 21
    # v0.7.2: structuredContent exposes NO jobs array — all 21 blocks are ONLY
    # in final_text, verified by the per-block assertions below.
    assert "jobs" not in result["structuredContent"]
    assert "evidence" not in result["structuredContent"]
    assert "final_text" in result["structuredContent"]

    # ── Split into 21 blocks by adjacent numbering ──
    # Find the start of section 4 (岗位列表) and end at section 5 (说明)
    sec4_start = text.index("【4·岗位列表】")
    sec5_start = text.index("【5·说明】")
    job_section = text[sec4_start:sec5_start]

    # Extract block boundaries: each block starts with "N. " where N is 1..21
    block_starts: list[int] = []
    for i in range(1, 22):
        marker = f"\n{i}. " if i > 1 else f"{i}. "
        block_starts.append(job_section.index(marker))

    blocks: list[str] = []
    for idx in range(21):
        start = block_starts[idx]
        end = block_starts[idx + 1] if idx + 1 < 21 else len(job_section)
        blocks.append(job_section[start:end].strip())

    assert len(blocks) == 21

    # ── Per-block assertions (from final_text only — no structured jobs) ──
    for i, block in enumerate(blocks, start=1):
        # Must start with correct number
        assert block.startswith(f"{i}. "), f"Block {i} does not start with '{i}. '"

        # Fact line must contain title and one unique company.
        assert "AI应用工程师" in block, f"Block {i} missing title"
        fact_fields = block.splitlines()[0].split("｜")
        company = fact_fields[1]
        assert company.startswith("示例科技"), f"Block {i} missing company"
        assert "上海" in block, f"Block {i} missing location"
        assert "社招" in block or "校招" in block or "招聘类型" in block, (
            f"Block {i} missing recruitment track"
        )
        employment_labels = ("正式", "实习", "兼职", "岗位性质")
        assert any(label in block for label in employment_labels), (
            f"Block {i} missing employment type"
        )
        assert "｜" in block, f"Block {i} missing pipe separators in fact line"

        # Match description line must be present
        assert "匹配度" in block, f"Block {i} missing match degree"

        # Independent 投递链接 with correct URL
        source_index = company.removeprefix("示例科技")
        expected_url = f"https://example.com/jobs/{source_index}"
        assert f"投递链接：{expected_url}" in block, (
            f"Block {i} missing or wrong apply URL: expected {expected_url}"
        )
        # The URL must appear on its own line (bare URL after 投递链接：)
        lines = block.split("\n")
        url_lines = [ln for ln in lines if "投递链接：" in ln]
        assert len(url_lines) >= 1, f"Block {i} has no 投递链接 line"

        # Recommendation reason must be present
        assert "推荐理由：" in block, f"Block {i} missing recommendation reason"
        # Recommendation must not be empty
        reason_pos = block.index("推荐理由：")
        reason_text = block[reason_pos + len("推荐理由：") :].strip()
        assert len(reason_text) > 0, f"Block {i} has empty recommendation reason"

    # Numbering must be consecutive in the original text
    for i in range(1, 21):
        pos_i = text.index(f"{i}. ")
        pos_next = text.index(f"{i + 1}. ")
        assert pos_i < pos_next, f"Block {i} and {i + 1} out of order"

    assert "workspace" not in text.casefold()
    assert "plan_id" not in text.casefold()


def test_no_resume_recommendation_contains_no_marketing_words(tmp_path) -> None:
    """In no-profile mode, the Server's 推荐理由 must be evidence-grounded
    and NEVER contain subjective evaluations like company reputation or
    area desirability."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent 3-5年 25-40K",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    # Server recommendation reason must be present
    assert "推荐理由：" in text

    # Forbidden marketing/subjective words — must not appear in Server output
    forbidden = [
        "龙头",
        "核心区",
        "有前景",
        "福利齐全",
        "行业领先",
        "知名企业",
        "独角兽",
        "大厂",
        "明星",
        "风口",
        "赛道",
    ]
    for word in forbidden:
        assert word not in text, f"Marketing word '{word}' found in Server output"

    # In no-profile mode, must not fabricate resume-based match percentage
    assert "本次未使用简历" in text
    # The match-degree line should use the no-profile form
    assert "已通过角色" in text or "非录用概率" in text


def test_search_output_section_headers_are_locked_and_immutable(tmp_path) -> None:
    """The five-section header structure is part of the output contract."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    required_headers = [
        "【1·简历解析】",
        "【2·检索概览】",
        "【3·过滤说明】",
        "【4·岗位列表】",
        "【5·说明】",
    ]
    for header in required_headers:
        assert header in text, f"Missing locked header: {header}"

    # The text must be the primary output channel
    assert isinstance(result["content"][0]["text"], str)
    assert len(result["content"][0]["text"]) > 0
    # v0.7.2: structuredContent is deliberately minimal — no jobs/evidence
    assert "final_text" in result["structuredContent"]
    assert "count" in result["structuredContent"]
    assert "changes" in result["structuredContent"]
    assert "diagnostic_summary" in result["structuredContent"]
    assert "integrity" in result["structuredContent"]
    assert "jobs" not in result["structuredContent"]
    assert "evidence" not in result["structuredContent"]
    assert "diagnostics" not in result["structuredContent"]


# ── v0.7.2: structuredContent isolation contract ──────────────────────────


def test_search_jobs_structured_content_excludes_jobs_evidence_jd(
    tmp_path,
) -> None:
    """structuredContent must NOT contain jobs, evidence, JD excerpts, or
    apply URLs that could induce the host model to rebuild the result."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent 大模型 3-5年 25-40K",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    sc = result["structuredContent"]

    # Must have the new top-level keys
    assert set(sc.keys()) == {
        "final_text",
        "count",
        "changes",
        "diagnostic_summary",
        "integrity",
    }

    # Must NOT contain jobs, evidence, JD, or apply_url at any nested depth
    serialized = json.dumps(sc, ensure_ascii=False)
    assert '"jobs"' not in serialized
    assert '"evidence"' not in serialized
    assert '"description"' not in serialized
    assert '"apply_url"' not in serialized
    assert '"job"' not in serialized
    assert '"score"' not in serialized

    # final_text is non-empty and contains the five-section structure
    assert len(sc["final_text"]) > 0
    assert "【1·简历解析】" in sc["final_text"]
    assert "【4·岗位列表】" in sc["final_text"]


def test_search_jobs_final_text_equals_content_text(tmp_path) -> None:
    """content[0].text must be byte-identical to structuredContent.final_text."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    content_text = result["content"][0]["text"]
    structured_final_text = result["structuredContent"]["final_text"]

    assert content_text == structured_final_text
    # Byte-level identity
    assert content_text.encode("utf-8") == structured_final_text.encode("utf-8")


def test_search_jobs_integrity_hash_matches(tmp_path) -> None:
    """The integrity.sha256 must be the SHA-256 hex digest of final_text."""
    import hashlib

    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    final_text = result["structuredContent"]["final_text"]
    expected_hash = hashlib.sha256(final_text.encode("utf-8")).hexdigest()
    actual_hash = result["structuredContent"]["integrity"]["sha256"]

    assert len(actual_hash) == 64
    assert actual_hash == expected_hash


def test_21_job_blocks_all_only_in_final_text(tmp_path) -> None:
    """All 21 job blocks exist ONLY in final_text, not in structured keys."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    records = [
        {
            "id": f"job-{i}",
            "title": "AI应用工程师",
            "company": f"示例科技{i}",
            "description": "Python RAG Agent 大模型 3-5年 25-40K",
            "location": "上海",
            "url": f"https://example.com/jobs/{i}",
        }
        for i in range(1, 22)
    ]
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(json.dumps(records, ensure_ascii=False), source_name="企业官网"),
    )

    result = registry.call("search_jobs", {"refresh_mode": "cache", "limit": 21})
    sc = result["structuredContent"]

    # All 21 job blocks are in final_text
    final_text = sc["final_text"]
    for i in range(1, 22):
        assert f"{i}. " in final_text
        assert f"示例科技{i}" in final_text
        assert f"投递链接：https://example.com/jobs/{i}" in final_text

    # No job data is repeated outside final_text.
    metadata = {key: value for key, value in sc.items() if key != "final_text"}
    serialized = json.dumps(metadata, ensure_ascii=False)
    for i in range(1, 22):
        assert f"示例科技{i}" not in serialized
        assert f"https://example.com/jobs/{i}" not in serialized


def test_get_jobs_still_works_normally(tmp_path) -> None:
    """get_jobs must still return full job summaries with apply URLs."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    result = registry.call("get_jobs", {"limit": 1})
    sc = result["structuredContent"]

    assert sc["count"] == 1
    assert len(sc["jobs"]) == 1
    job = sc["jobs"][0]
    assert job["title"] == "AI应用工程师"
    assert job["company"] == "示例科技"
    assert job["apply_url"] == "https://example.com/jobs/1"
    assert "投递链接：https://example.com/jobs/1" in result["content"][0]["text"]


def test_get_job_details_still_works_normally(tmp_path) -> None:
    """get_job_details must still return full job descriptions."""
    core, workspace, _, registry = make_registry(tmp_path)
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent 大模型应用开发",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    page = registry.call("get_jobs", {"limit": 1})["structuredContent"]
    job_id = page["jobs"][0]["job_id"]
    details = registry.call("get_job_details", {"job_id": job_id})["structuredContent"]

    assert details["job"]["title"] == "AI应用工程师"
    assert "Python RAG Agent" in details["job"]["description"]
    assert details["job"]["apply_url"] == "https://example.com/jobs/1"
    assert details["untrusted_external_content"] is True


# ── v0.7.2: use_profile regression ────────────────────────────────────────


def test_use_profile_false_with_existing_profile_shows_no_resume_section_1(
    tmp_path,
) -> None:
    """use_profile=false must skip profile entirely — Section 1 shows
    '本次未使用简历', no match percentages appear, and the local profile
    is NOT deleted (remains queryable)."""
    core, workspace, _, registry = make_registry(tmp_path)

    # Set up a confirmed profile
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：Python、RAG\n项目：内部项目ABC\n经验：5年\n学历：硕士",
        encoding="utf-8",
    )
    registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
        },
    )

    # Import a job
    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent 3-5年 25-40K",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    # Search with use_profile=false
    result = registry.call(
        "search_jobs",
        {"refresh_mode": "cache", "use_profile": False},
    )
    text = result["content"][0]["text"]
    profile_section = text.split("【2·检索概览】", maxsplit=1)[0]

    # Section 1 must show no-resume
    assert "【1·简历解析】" in text
    assert "本次未使用简历" in text
    # Must NOT show profile counts
    assert "技能 2 项" not in profile_section
    assert "项目 1 项" not in profile_section
    assert "经验 1 项" not in profile_section
    assert "学历：硕士" not in profile_section
    assert "Python" not in profile_section
    assert "内部项目ABC" not in profile_section

    # No match percentage (no-resume mode)
    assert "匹配度：已通过角色、地点、薪资等可判定硬条件" in text
    # Must NOT have a percentage match line
    assert not re.search(r"匹配度：\d+%", text)

    # Recommendation reason must be no-resume based
    assert "推荐理由：" in text
    assert "本次未使用简历" in text or "按明确条件匹配" in text

    # structuredContent contract unchanged
    sc = result["structuredContent"]
    assert "jobs" not in sc
    assert "evidence" not in sc
    assert "final_text" in sc

    # Profile still exists (NOT deleted)
    profile_result = registry.call(
        "setup_profile",
        {
            "action": "review",
            "workspace_id": workspace.workspace_id,
            "profile_id": core.profiles.latest_confirmed_summary(
                workspace_id=workspace.workspace_id
            ).profile_id,
        },
    )
    assert profile_result["isError"] is False
    assert profile_result["structuredContent"]["total_facts"] > 0


def test_use_profile_true_default_preserves_existing_behavior(tmp_path) -> None:
    """Default use_profile=true must behave exactly as before — profile counts
    in Section 1 and match percentages when profile exists."""
    core, workspace, _, registry = make_registry(tmp_path)

    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG\n学历：硕士", encoding="utf-8")
    registry.call(
        "setup_profile",
        {
            "action": "import",
            "workspace_id": workspace.workspace_id,
            "resume_path": str(resume),
        },
    )

    from jobfindsme.importing.parsers import parse_json

    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent 3-5年 25-40K",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    # Default (no use_profile arg) = use_profile=true
    result = registry.call("search_jobs", {"refresh_mode": "cache"})
    text = result["content"][0]["text"]

    # Section 1 must show profile counts
    assert "【1·简历解析】" in text
    assert "技能 2 项" in text
    # Must NOT be the no-resume line
    assert "本次未使用简历" not in text
    assert re.search(r"匹配度：\d+%", text)

    # Explicit use_profile=true gives same result
    result2 = registry.call(
        "search_jobs", {"refresh_mode": "cache", "use_profile": True}
    )
    profile_section = text.split("【2·检索概览】", maxsplit=1)[0]
    second_profile_section = result2["content"][0]["text"].split(
        "【2·检索概览】", maxsplit=1
    )[0]
    assert second_profile_section == profile_section


def test_use_profile_false_without_profile_still_shows_no_resume(tmp_path) -> None:
    """use_profile=false without any profile is a no-op — still shows
    '本次未使用简历' (no crash, no error)."""
    _, _, _, registry = make_registry(tmp_path)

    result = registry.call(
        "search_jobs", {"refresh_mode": "cache", "use_profile": False}
    )
    text = result["content"][0]["text"]

    assert result["isError"] is False
    assert "【1·简历解析】" in text
    assert "本次未使用简历" in text


# ── v0.7.2: Chrome error sanitization ─────────────────────────────────────


def test_chrome_cdp_errors_normalized_to_recovery_message(tmp_path) -> None:
    """Chrome/CDP/9222 errors must be normalized to 'Chrome 未连接，请运行
    jobfindsme setup' — raw commands, port numbers, and stack traces must
    never leak into the user-facing output or diagnostic summary."""
    from jobfindsme.presentation import _short_error

    # Direct _short_error tests
    chrome_errors = [
        "Cannot connect to Chrome at ws://127.0.0.1:9222/devtools/browser",
        "CDP connection refused on port 9222",
        "chrome-debug error: websocket closed",
        "Chrome DevTools protocol error",
        "open -a Google Chrome --remote-debugging-port=9222 failed",
        "connection to 127.0.0.1:9222 timed out",
    ]
    normalized = "Chrome 未连接，请运行 jobfindsme setup"
    for err in chrome_errors:
        assert _short_error(err) == normalized, f"Failed for: {err}"

    # Non-Chrome errors get short category labels
    assert _short_error("request timed out after 30s") == "来源响应超时"
    assert _short_error("Connection refused") == "来源无法连接"
    assert _short_error("authentication required, please login") == "来源需要登录"
    assert _short_error("JSON parse error at line 1") == "来源返回数据无法解析"

    # Generic fallback is truncated
    generic = "Some unknown internal processing failure"
    assert len(_short_error(generic)) <= 60
    assert _short_error(None) == "无结果"


def test_source_summary_never_leaks_raw_chrome_command(tmp_path) -> None:
    """The diagnostic_summary.source_summary must sanitize Chrome errors
    so the host model never sees raw CDP commands or port numbers."""
    from jobfindsme.mcp.responses import build_source_summary

    diagnostics = {
        "refresh_mode": "fast",
        "source_runs": [
            {
                "source_name": "BOSS直聘",
                "status": "failed",
                "error": (
                    "Cannot connect to Chrome at ws://127.0.0.1:9222/devtools/"
                    "browser — open -a Google Chrome --remote-debugging-port=9222 "
                    "--remote-allow-origins=http://127.0.0.1:9222"
                ),
                "discovered": 0,
            },
            {
                "source_name": "猎聘",
                "status": "success",
                "discovered": 42,
                "cache_used": False,
            },
        ],
    }
    summary = build_source_summary(diagnostics)

    # Chrome error normalized
    assert "Chrome 未连接，请运行 jobfindsme setup" in summary
    # Raw command NOT leaked
    assert "remote-debugging-port" not in summary
    assert "9222" not in summary
    assert "Google Chrome" not in summary
    assert "websocket" not in summary.casefold()
    # Successful source appears normally
    assert "猎聘 ✓(42)" in summary


def test_search_result_rendered_output_sanitizes_chrome_errors(tmp_path) -> None:
    """End-to-end: a search with a failed Chrome source must show the
    normalized recovery message, never raw CDP/Chrome commands."""
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
    text = result["content"][0]["text"]

    # Error appears but is safe
    assert "【2·检索概览】" in text
    # Raw error details NOT exposed
    assert "remote-debugging-port" not in text
    assert "9222" not in text
    assert "Traceback" not in text


# ── v0.7.2: STOP contract — structuredContent isolation ───────────────────


def test_structured_content_remains_slim_with_use_profile_false(tmp_path) -> None:
    """structuredContent must remain slim (5 keys, no jobs/evidence) even
    when use_profile=false."""
    _, _, _, registry = make_registry(tmp_path)

    result = registry.call(
        "search_jobs", {"refresh_mode": "cache", "use_profile": False}
    )
    sc = result["structuredContent"]

    assert set(sc.keys()) == {
        "final_text",
        "count",
        "changes",
        "diagnostic_summary",
        "integrity",
    }
    serialized = json.dumps(sc, ensure_ascii=False)
    assert '"jobs"' not in serialized
    assert '"evidence"' not in serialized
    assert '"description"' not in serialized
    assert '"apply_url"' not in serialized


def test_search_jobs_validation_rejects_unknown_fields_preserves_use_profile(
    tmp_path,
) -> None:
    """Extra fields still rejected; use_profile is now a known field."""
    _, workspace, _, registry = make_registry(tmp_path)

    # Extra field still rejected
    result = registry.call(
        "search_jobs",
        {"workspace_id": workspace.workspace_id, "extra_field": True},
    )
    assert result["isError"] is True

    # use_profile is accepted
    result2 = registry.call(
        "search_jobs",
        {"refresh_mode": "cache", "use_profile": False},
    )
    assert result2["isError"] is False
    assert "final_text" in result2["structuredContent"]
