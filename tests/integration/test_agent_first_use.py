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
    call(registry, "configure_monitor", enabled=True, interval_hours=24)
    receipt = call(registry, "export_local_data")

    assert Path(receipt["path"]).exists()
