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
        "setup",
        "search_jobs",
        "get_jobs",
        "update_job_state",
        "delete_local_data",
    ]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
    assert all(tool["title"] for tool in tools)
    # get_jobs deliberately has no outputSchema: it returns either a
    # JobSummary list or a JobDetails payload depending on job_id.
    assert {tool["name"] for tool in tools if "outputSchema" not in tool} == {
        "get_jobs"
    }
    assert all(
        tool["outputSchema"]["type"] == "object"
        for tool in tools
        if "outputSchema" in tool
    )
    assert all("annotations" in tool for tool in tools)
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["search_jobs"]["annotations"]["openWorldHint"] is True
    assert by_name["delete_local_data"]["annotations"]["destructiveHint"] is True


def test_first_use_does_not_require_workspace_or_plan_ids(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")

    imported = registry.call(
        "setup",
        {"resume_path": str(resume)},
    )
    configured = registry.call(
        "setup",
        {
            "target_roles": ["AI应用工程师"],
            "locations": ["上海"],
        },
    )
    searched = registry.call("search_jobs", {})

    assert imported["isError"] is False
    assert configured["isError"] is False
    assert configured["structuredContent"]["plan"]["preferences"]["target_roles"] == [
        "AI应用工程师"
    ]
    assert searched["isError"] is False
    # Search may return live results or be empty — both are valid
    assert isinstance(searched["structuredContent"]["summary"], str)
    assert isinstance(searched["structuredContent"]["count"], int)
    assert "jobs" in searched["structuredContent"]
    assert "diagnostic_summary" in searched["structuredContent"]
    assert core.list_workspaces()


def test_setup_persists_recruitment_and_employment_filters(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)

    result = registry.call(
        "setup",
        {
            "target_roles": ["AI应用工程师"],
            "locations": ["上海", "杭州"],
            "recruitment_track": "social",
            "employment_type": "full_time",
        },
    )

    plan = result["structuredContent"]["plan"]["preferences"]
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
    registry._definitions["setup"] = replace(
        registry._definitions["setup"],
        output_model=GetJobsOutput,
    )

    result = registry.call(
        "setup",
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


def test_profile_import_is_paginated_instead_of_dumping_all_facts(tmp_path) -> None:
    _, _, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：" + "、".join(["Python", "RAG", "Agent", "MCP", "Docker", "Redis"]),
        encoding="utf-8",
    )

    imported = registry.call(
        "setup",
        {
            "resume_path": str(resume),
            "auto_confirm": False,
            "limit": 2,
        },
    )["structuredContent"]

    assert len(imported["facts"]) == 2
    assert imported["total_facts"] >= 6
    assert imported["next_offset"] == 2
    assert "fact_counts" in imported


def test_profile_import_auto_confirms_by_default_for_fast_first_use(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")

    result = registry.call(
        "setup",
        {"resume_path": str(resume)},
    )

    profile = result["structuredContent"]
    assert result["isError"] is False
    assert profile["profile_status"] == "confirmed"
    assert profile["facts"] == []
    assert profile["total_facts"] >= 2
    assert profile["fact_counts"]["skill"] >= 2
    assert profile["next_offset"] == 0
    assert profile["review_available"] is True
    assert "suggested_plan" not in profile


def test_job_list_bounds_context_and_omits_full_jd(tmp_path) -> None:
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

    # List mode must stay compact — full JD text lives behind an explicit
    # get_jobs({"job_id": ...}) call, never in the summaries.
    assert len(summaries[0].description_excerpt) <= 400
    assert "description" not in summaries[0].model_dump()
    assert summaries[0].untrusted_external_content is True
    assert summaries[0].recruitment_track == "social"
    assert summaries[0].employment_type == "full_time"
    assert page["count"] == 1
    assert page["offset"] == 0
    assert page["limit"] == 1
    assert page["next_offset"] == 1
    assert (
        page["jobs"][0].apply_url
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
    # Step 2: bounded facts are exposed for the host to present
    assert len(result["structuredContent"]["jobs"]) == 1
    assert "evidence" in result["structuredContent"]["jobs"][0]
    assert "summary" in result["structuredContent"]


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
        "setup",
        {
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
    # v0.7.2: profile_used is now only in summary section 1, not structuredContent
    assert "简历解析：技能" in text


def test_search_sparse_jd_with_profile_keeps_score_in_60_to_100(tmp_path) -> None:
    """Even a sparse JD keeps a 60%+ score (hard-condition floor)."""
    core, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python", encoding="utf-8")
    registry.call(
        "setup",
        {
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

    assert re.search(r"匹配度：6\d%|匹配度：100%", text)


def test_search_reason_lists_matched_and_missing_skills(tmp_path) -> None:
    """推荐理由 must name resume skills that hit and JD skills that are missing."""
    core, workspace, _, registry = make_registry(tmp_path)
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")
    registry.call(
        "setup",
        {
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

    assert "匹配度：78%（信号匹配，非录用概率）" in text
    assert "简历技能命中：Python、RAG" in text
    assert "岗位要求但简历未体现：Kubernetes" in text


def test_search_operating_summary_lists_results_suggestions_and_next_steps(
    tmp_path,
) -> None:
    """⑤ 说明 must render results, suggestions, next steps, and apply tip."""
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
    assert "结果：历史共匹配 1 个合适岗位" in first_text
    assert "本次展示 1 个（全部新增）" in first_text
    assert "累计展示 1 次" in first_text
    assert "建议：优先投 #1（示例科技" in first_text
    assert "下一步建议（和 AI 聊天就能用）：" in first_text
    assert "📬 定时推送" in first_text
    assert "📋 查看历史" in first_text
    assert "投递后对我说「把第 1 个标记为已投递」" in first_text
    assert "重复抑制" not in first_text

    second = registry.call(
        "search_jobs", {"refresh_mode": "cache", "include_seen": False}
    )
    second_text = second["content"][0]["text"]
    assert "本次展示 0 个（无新增）" in second_text
    assert "重复抑制（此前展示且未变化）1 条" in second_text
    assert "建议：当前没有可投递的新岗位" in second_text


def test_search_distinguishes_source_failure_from_no_delta(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    registry.call(
        "setup",
        {"target_roles": ["AI应用工程师"]},
    )

    # The broken source is passed on the search call itself — explicit
    # sources on setup are not exercised because the src handler passes
    # them as raw dicts to core.configure_search.
    result = registry.call(
        "search_jobs",
        {
            "refresh_mode": "full",
            "sources": [
                {
                    "kind": "json_file",
                    "source_name": "损坏来源",
                    "path": str(tmp_path / "missing.json"),
                }
            ],
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["count"] == 0
    assert "来源刷新失败" in result["content"][0]["text"]


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
    # in summary, verified by the per-block assertions below.
    assert len(result["structuredContent"]["jobs"]) == 21
    assert all("evidence" in fact for fact in result["structuredContent"]["jobs"])
    assert "summary" in result["structuredContent"]

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

    # ── Per-block assertions (from summary only — no structured jobs) ──
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
    # Step 2: summary + bounded facts; full diagnostics stay server-side
    assert "summary" in result["structuredContent"]
    assert "count" in result["structuredContent"]
    assert "changes" in result["structuredContent"]
    assert "diagnostic_summary" in result["structuredContent"]
    assert "jobs" in result["structuredContent"]
    assert "diagnostics" not in result["structuredContent"]


# ── Step 2: structured facts contract ─────────────────────────────────────


def test_search_jobs_structured_content_exposes_bounded_facts(tmp_path) -> None:
    """structuredContent exposes bounded job facts (no full JD text)."""
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
        "summary",
        "count",
        "jobs",
        "changes",
        "diagnostic_summary",
    }

    # Facts are bounded: apply URLs present, full JD text absent
    serialized = json.dumps(sc, ensure_ascii=False)
    assert '"jobs"' in serialized
    assert '"evidence"' in serialized
    assert '"apply_url"' in serialized
    assert '"description"' not in serialized

    # summary is non-empty and contains the five-section baseline
    assert len(sc["summary"]) > 0
    assert "【1·简历解析】" in sc["summary"]
    assert "【4·岗位列表】" in sc["summary"]

    fact = sc["jobs"][0]
    assert fact["job"]["title"] == "AI应用工程师"
    assert fact["job"]["apply_url"] == "https://example.com/jobs/1"
    assert "description" not in fact["job"]


def test_search_jobs_summary_equals_content_text(tmp_path) -> None:
    """content[0].text must be byte-identical to structuredContent.summary."""
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
    structured_summary = result["structuredContent"]["summary"]

    assert content_text == structured_summary
    # Byte-level identity
    assert content_text.encode("utf-8") == structured_summary.encode("utf-8")


def test_21_job_blocks_appear_in_summary_and_structured_jobs(tmp_path) -> None:
    """All 21 job blocks exist in summary AND as structured job facts."""
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

    # All 21 job blocks are in summary
    summary = sc["summary"]
    for i in range(1, 22):
        assert f"{i}. " in summary
        assert f"示例科技{i}" in summary
        assert f"投递链接：https://example.com/jobs/{i}" in summary

    # Structured facts carry every apply URL as well
    facts = {fact["job"]["company"]: fact["job"]["apply_url"] for fact in sc["jobs"]}
    assert len(facts) == 21
    for i in range(1, 22):
        assert f"示例科技{i}" in facts
        assert facts[f"示例科技{i}"] == f"https://example.com/jobs/{i}"


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
    assert job.title == "AI应用工程师"
    assert job.company == "示例科技"
    assert job.apply_url == "https://example.com/jobs/1"
    assert "投递链接：https://example.com/jobs/1" in result["content"][0]["text"]


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
        "setup",
        {
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

    # structured facts exposed, bounded
    sc = result["structuredContent"]
    assert "jobs" in sc
    assert "summary" in sc

    # Profile still exists (NOT deleted)
    profile_result = registry.call(
        "setup",
        {
            "resume_path": str(resume),
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
        "setup",
        {
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
    assert "猎聘 ✓ 42" in summary


def test_source_summary_aggregates_platforms_and_shows_coverage() -> None:
    from jobfindsme.mcp.responses import build_source_summary

    diagnostics = {
        "refresh_mode": "full",
        "source_runs": [
            {
                "source_name": "猎聘·深圳",
                "status": "success",
                "discovered": 42,
                "cache_used": False,
            },
            {
                "source_name": "猎聘·上海",
                "status": "success",
                "discovered": 42,
                "cache_used": False,
            },
            {
                "source_name": "BOSS直聘·上海",
                "status": "degraded",
                "discovered": 0,
                "cache_used": True,
            },
            {
                "source_name": "BOSS直聘·深圳",
                "status": "degraded",
                "discovered": 0,
                "cache_used": True,
            },
            {
                "source_name": "智联招聘·上海",
                "status": "degraded",
                "discovered": 0,
                "cache_used": True,
            },
            {
                "source_name": "前程无忧·上海",
                "status": "degraded",
                "discovered": 0,
                "cache_used": True,
            },
        ],
    }

    summary = build_source_summary(diagnostics)

    assert summary.count("猎聘") == 1
    assert summary.count("BOSS直聘") == 1
    assert summary.count("智联招聘") == 1
    assert summary.count("前程无忧") == 1
    assert "猎聘 ✓ 84（深圳42、上海42）" in summary
    assert "BOSS直聘 △ 缓存" in summary


def test_search_result_rendered_output_sanitizes_chrome_errors(tmp_path) -> None:
    """End-to-end: a search with a failed Chrome source must show the
    normalized recovery message, never raw CDP/Chrome commands."""
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    registry.call(
        "setup",
        {"target_roles": ["AI应用工程师"]},
    )

    result = registry.call(
        "search_jobs",
        {
            "refresh_mode": "full",
            "sources": [
                {
                    "kind": "json_file",
                    "source_name": "损坏来源",
                    "path": str(tmp_path / "missing.json"),
                }
            ],
        },
    )
    text = result["content"][0]["text"]

    # Error appears but is safe
    assert "【2·检索概览】" in text
    # Raw error details NOT exposed
    assert "remote-debugging-port" not in text
    assert "9222" not in text
    assert "Traceback" not in text


# ── Step 2: bounded facts contract ─────────────────────────────────────────


def test_structured_content_stays_bounded_with_empty_results(tmp_path) -> None:
    """structuredContent stays bounded (no full JD) even with zero results."""
    _, _, _, registry = make_registry(tmp_path)

    result = registry.call(
        "search_jobs", {"refresh_mode": "cache", "use_profile": False}
    )
    sc = result["structuredContent"]

    assert set(sc.keys()) == {
        "summary",
        "count",
        "jobs",
        "changes",
        "diagnostic_summary",
    }
    serialized = json.dumps(sc, ensure_ascii=False)
    assert sc["jobs"] == []
    assert '"description"' not in serialized


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
    assert "summary" in result2["structuredContent"]
