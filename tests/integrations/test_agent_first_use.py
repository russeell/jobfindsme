from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from jobfindsme.app import jobfindsmecore
from jobfindsme.contracts import (
    EmploymentType,
    JobLiveness,
    JobSummary,
    RecruitmentTrack,
    SalaryDetails,
    SalaryPeriod,
)
from jobfindsme.mcp import ToolRegistry
from jobfindsme.presentation import format_job_list


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
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)

    profile = call(registry, "setup", resume_path=str(resume))
    assert profile["profile_status"] == "confirmed"
    call(
        registry,
        "setup",
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
    assert search_result["count"] == 2
    assert len(search_result["jobs"]) == 2
    assert "甲公司" in search_result["summary"]
    assert "乙公司" in search_result["summary"]

    history = call(registry, "get_jobs", limit=10)
    matches = history["jobs"]
    companies = {item.company for item in matches}
    assert companies == {"甲公司", "乙公司"}
    summary = matches[0].model_dump()
    assert "description" not in summary
    assert summary["untrusted_external_content"] is True

    call(
        registry,
        "update_job_state",
        job_id=matches[0].job_id,
        state="saved",
    )
    export_path = tmp_path / "export.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "jobfindsme",
            "--db",
            str(tmp_path / "jobfindsme.db"),
            "export",
            "--workspace",
            core.context.resolve_workspace().workspace_id,
            "--path",
            str(export_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        # Resolve the src-layout package from the repo regardless of how (or
        # whether) the current interpreter has jobfindsme installed.
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
        },
    )
    assert completed.returncode == 0, completed.stderr

    assert export_path.exists()


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
        "setup",
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
    assert structured["summary"] == rendered
    assert len(structured["jobs"]) == 1
    history_companies = {
        item.company for item in call(registry, "get_jobs", limit=10)["jobs"]
    }
    assert history_companies == {"甲公司", "乙公司"}
    assert "乙公司" not in rendered
    assert "匹配度：" in rendered
    assert "推荐理由：" in rendered
    assert "投递链接：https://example.com/jobs/qualified" in rendered
    assert "本轮远程发现 2 条，本地岗位库匹配到 1 条" in rendered
    assert "workspace_id" not in rendered
    assert "plan_id" not in rendered
    assert "│" not in rendered

    second = registry.call(
        "search_jobs", {"refresh_mode": "cache", "include_seen": False}
    )
    assert second["isError"] is False
    second_text = second["content"][0]["text"]
    assert all(f"【{index}·" in second_text for index in range(1, 6))
    assert "本轮未刷新外部来源，从本地缓存匹配到 0 条" in second_text
    assert "此前展示且未变化" in second_text
    assert "重复岗位" not in second_text


def test_undisclosed_salary_never_claims_salary_is_explicit() -> None:
    """Source text wins if stale numeric fields conflict with '面议'."""
    job = JobSummary(
        job_id="job-undisclosed",
        title="AI应用工程师",
        company="乙公司",
        locations=("上海",),
        salary=SalaryDetails(
            raw_text="薪资面议",
            currency="CNY",
            period=SalaryPeriod.MONTH,
            min_amount=20,
            max_amount=30,
        ),
        recruitment_track=RecruitmentTrack.SOCIAL,
        employment_type=EmploymentType.FULL_TIME,
        apply_url="https://example.com/jobs/undisclosed",
        source_name="测试来源",
        liveness=JobLiveness.ACTIVE,
    )

    rendered = format_job_list([job], include_recommendation=True)

    assert "需要注意：薪资未注明" in rendered
    assert "薪资信息明确" not in rendered
