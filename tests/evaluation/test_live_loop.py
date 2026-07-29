from __future__ import annotations

import json
from pathlib import Path

from jobfindsme.contracts import DiscoverySource, SourceRunStatus
from jobfindsme.core import jobfindsmecore
from jobfindsme.evaluation.live_loop import run_live_search_loop, write_loop_report


def _configured_core(tmp_path: Path) -> jobfindsmecore:
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(
        json.dumps(
            [
                {
                    "title": "AI应用工程师",
                    "company": "示例科技",
                    "description": "Python RAG Agent",
                    "location": "上海",
                    "salary": "20-30K",
                    "url": "https://jobs.example.com/ai-1",
                    "recruitment_track": "social",
                    "employment_type": "full_time",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("Loop Test")
    core.configure_search(
        workspace_id=workspace.workspace_id,
        target_roles=("AI应用工程师",),
        locations=("上海",),
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="local-fixture",
                path=str(jobs_path),
            ),
        ),
    )
    return core


def test_live_loop_records_search_counts_timings_and_quality(tmp_path: Path) -> None:
    report = run_live_search_loop(
        _configured_core(tmp_path),
        agent_host="pytest",
        allow_browser_sources=False,
    )

    assert report.agent_host == "pytest"
    assert report.diagnostics.total_discovered == 1
    assert report.diagnostics.total_unique == 1
    assert report.diagnostics.result_count == 1
    assert report.diagnostics.elapsed_seconds >= 0
    assert report.diagnostics.source_runs[0].status is SourceRunStatus.SUCCESS
    assert report.quality.source_success_rate == 1
    assert report.quality.url_shape_valid_rate == 1
    assert report.quality.required_field_complete_rate == 1
    assert report.jobs[0].apply_url == "https://jobs.example.com/ai-1"


def test_live_loop_report_excludes_resume_and_full_job_description(
    tmp_path: Path,
) -> None:
    report = run_live_search_loop(
        _configured_core(tmp_path),
        agent_host="codex",
        allow_browser_sources=False,
    )
    output = write_loop_report(tmp_path / "loop.json", report)
    payload = output.read_text(encoding="utf-8")

    assert "Python RAG Agent" not in payload
    assert "profile_hash" in payload
    assert '"apply_url": "https://jobs.example.com/ai-1"' in payload


def test_live_loop_records_source_failure_without_fake_success(tmp_path: Path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("Failure Test")
    core.configure_search(
        workspace_id=workspace.workspace_id,
        target_roles=("AI应用工程师",),
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="missing-source",
                path=str(tmp_path / "missing.json"),
            ),
        ),
    )

    report = run_live_search_loop(
        core,
        agent_host="pytest",
        allow_browser_sources=False,
    )

    assert report.diagnostics.source_runs[0].status is SourceRunStatus.FAILED
    assert report.quality.source_success_rate == 0
    assert report.quality.automatic_findings
    assert report.jobs == ()


def test_live_loop_excludes_jobs_from_previous_source_configuration(
    tmp_path: Path,
) -> None:
    core = _configured_core(tmp_path)
    first_report = run_live_search_loop(
        core,
        agent_host="pytest",
        allow_browser_sources=False,
    )
    assert len(first_report.jobs) == 1

    context = core.context.resolve(require_plan=True)
    core.configure_search(
        workspace_id=context.workspace.workspace_id,
        plan_id=context.plan.plan_id if context.plan else None,
        target_roles=("AI应用工程师",),
        locations=("上海",),
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="replacement-source",
                path=str(tmp_path / "missing.json"),
            ),
        ),
    )

    second_report = run_live_search_loop(
        core,
        agent_host="pytest",
        allow_browser_sources=False,
    )

    assert second_report.jobs == ()
    assert second_report.quality.unexpected_result_sources == ()
