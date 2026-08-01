from __future__ import annotations

import json
from pathlib import Path

from jobfindsme.core import jobfindsmecore
from jobfindsme.mcp import ToolRegistry


def call(registry: ToolRegistry, name: str, **arguments):
    result = registry.call(name, arguments)
    assert result["isError"] is False, result
    return result["structuredContent"]


def test_agent_completes_first_use_without_internal_ids(tmp_path) -> None:
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：Python、RAG、FastAPI\n项目经历\n- 使用 FastAPI 构建 RAG 服务",
        encoding="utf-8",
    )
    jobs = tmp_path / "jobs.json"
    jobs.write_text(
        json.dumps(
            [
                {
                    "id": "python",
                    "title": "AI应用工程师",
                    "company": "甲公司",
                    "location": "上海",
                    "description": "Python FastAPI RAG，20-30K·13薪",
                    "url": "https://example.com/jobs/python",
                },
                {
                    "id": "java",
                    "title": "AI应用工程师",
                    "company": "乙公司",
                    "location": "上海",
                    "description": "Java Spring，20-30K",
                    "url": "https://example.com/jobs/java",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    registry = ToolRegistry(jobfindsmecore(tmp_path / "jobfindsme.db"))

    profile = call(
        registry,
        "setup_profile",
        action="import",
        resume_path=str(resume),
    )
    assert profile["status"] == "confirmed"
    call(
        registry,
        "configure_search",
        target_roles=["AI应用工程师"],
        locations=["上海"],
        sources=[
            {
                "kind": "json_file",
                "source_name": "用户提供岗位",
                "path": str(jobs),
            }
        ],
    )
    search_result = call(registry, "search_jobs")
    matches = search_result["jobs"]

    assert search_result["count"] == 2
    # v0.4: filter-only, no BM25 ranking — both jobs pass hard filter.
    # Order is insertion order; the Agent owns ranking.
    companies = {m["job"]["company"] for m in matches}
    assert companies == {"甲公司", "乙公司"}
    # v0.4: evidence carries extracted_signals for Agent-side matching,
    # not BM25 profile-based evidence_pairs/matched_profile_skills.
    for m in matches:
        assert "extracted_signals" in m["evidence"]
        sig = m["evidence"]["extracted_signals"]
        assert isinstance(sig["required_skills"], list)
    assert "description" not in matches[0]["job"]
    assert matches[0]["job"]["untrusted_external_content"] is True

    call(
        registry,
        "update_job_state",
        job_id=matches[0]["job"]["job_id"],
        state="saved",
    )
    receipt = call(registry, "export_local_data")

    assert Path(receipt["path"]).exists()


def test_search_text_is_complete_and_stable_for_agent_hosts(tmp_path) -> None:
    jobs = tmp_path / "jobs.json"
    jobs.write_text(
        json.dumps(
            [
                {
                    "id": "qualified",
                    "title": "AI应用工程师",
                    "company": "甲公司",
                    "location": "上海",
                    "description": "Python FastAPI RAG Agent，20-30K，社招正式岗。",
                    "recruitment_track": "social",
                    "employment_type": "full_time",
                    "url": "https://example.com/jobs/qualified",
                },
                {
                    "id": "unknown-salary",
                    "title": "AI应用工程师",
                    "company": "乙公司",
                    "location": "上海",
                    "description": "Python RAG Agent，薪资面议，社招正式岗。",
                    "recruitment_track": "social",
                    "employment_type": "full_time",
                    "url": "https://example.com/jobs/unknown-salary",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    registry = ToolRegistry(jobfindsmecore(tmp_path / "jobfindsme.db"))
    call(
        registry,
        "configure_search",
        target_roles=["AI应用工程师"],
        locations=["上海"],
        salary_min_k=20,
        recruitment_track="social",
        employment_type="full_time",
        sources=[
            {
                "kind": "json_file",
                "source_name": "用户提供岗位",
                "path": str(jobs),
            }
        ],
    )

    first = registry.call("search_jobs", {"refresh_mode": "full"})
    assert first["isError"] is False
    rendered = first["content"][0]["text"]
    structured = first["structuredContent"]

    section_positions = [rendered.index(f"【{index}·") for index in range(1, 6)]
    assert section_positions == sorted(section_positions)
    assert structured["count"] == 1
    assert structured["jobs"][0]["job"]["company"] == "甲公司"
    assert "乙公司" not in rendered
    assert "匹配度：" in rendered
    assert "推荐理由：" in rendered
    assert "投递链接：https://example.com/jobs/qualified" in rendered
    assert "workspace_id" not in rendered
    assert "plan_id" not in rendered
    assert "│" not in rendered

    second = registry.call("search_jobs", {"refresh_mode": "cache"})
    assert second["isError"] is False
    second_text = second["content"][0]["text"]
    assert all(f"【{index}·" in second_text for index in range(1, 6))
    assert "本轮未刷新外部来源，使用本地缓存" in second_text
    assert "此前展示且未变化" in second_text
    assert "重复岗位" not in second_text
