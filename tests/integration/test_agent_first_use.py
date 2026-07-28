from __future__ import annotations

import json
from pathlib import Path

from jobfindsme.core import JobFindsMeCore
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
    registry = ToolRegistry(JobFindsMeCore(tmp_path / "jobfindsme.db"))

    profile = call(
        registry,
        "setup_profile",
        action="import",
        resume_path=str(resume),
    )
    call(
        registry,
        "setup_profile",
        action="confirm",
        profile_id=profile["profile_id"],
        accepted_fact_ids=[fact["fact_id"] for fact in profile["facts"]],
    )
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
    matches = call(registry, "search_jobs")

    assert matches[0]["job"]["company"] == "甲公司"
    assert matches[0]["evidence"]["matched_profile_skills"] == [
        "FastAPI",
        "Python",
        "RAG",
    ]
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
