from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jobfindsme.contracts import (
    SearchRunDiagnostics,
    SourceRunStats,
    SourceRunStatus,
)
from jobfindsme.evaluation.improvement import analyze_engineering_improvements
from jobfindsme.evaluation.live_loop import (
    LiveSearchLoopReport,
    LoopJob,
    LoopQuality,
)


def _report(
    index: int,
    *,
    source_status: SourceRunStatus = SourceRunStatus.SUCCESS,
    elapsed: float = 5,
    complete: float = 1,
    unknown_type: float = 0,
    duplicate_urls: int = 0,
    with_job: bool = True,
) -> LiveSearchLoopReport:
    now = datetime(2026, 7, 29, tzinfo=UTC) + timedelta(days=index)
    job = LoopJob(
        rank=1,
        job_id=f"job-{index}",
        source_name="测试来源",
        title="AI应用工程师",
        company="示例科技",
        location="上海",
        score=0.8,
        recruitment_track="social",
        employment_type="full_time",
        apply_url=f"https://jobs.example.com/{index}",
    )
    return LiveSearchLoopReport(
        run_id=f"loop-{index}",
        agent_host="pytest",
        workspace_id="workspace",
        plan_id="plan",
        generated_at=now,
        diagnostics=SearchRunDiagnostics(
            started_at=now,
            finished_at=now + timedelta(seconds=elapsed),
            elapsed_seconds=elapsed,
            matching_seconds=0.1,
            source_runs=(
                SourceRunStats(
                    source_name="测试来源",
                    source_kind="json_file",
                    status=source_status,
                    elapsed_seconds=elapsed,
                    discovered=1 if source_status is SourceRunStatus.SUCCESS else 0,
                    unique=1 if source_status is SourceRunStatus.SUCCESS else 0,
                ),
            ),
            total_discovered=1 if source_status is SourceRunStatus.SUCCESS else 0,
            total_unique=1 if source_status is SourceRunStatus.SUCCESS else 0,
            result_count=1 if with_job else 0,
        ),
        quality=LoopQuality(
            source_success_rate=(1 if source_status is SourceRunStatus.SUCCESS else 0),
            url_shape_valid_rate=1 if with_job else 0,
            required_field_complete_rate=complete,
            unknown_track_rate=0,
            unknown_employment_type_rate=unknown_type,
            duplicate_apply_urls=duplicate_urls,
            average_match_score=0.8 if with_job else 0,
        ),
        jobs=(job,) if with_job else (),
    )


def test_healthy_operational_runs_still_require_human_evidence() -> None:
    result = analyze_engineering_improvements(tuple(_report(i) for i in range(3)))

    assert result.rapid_feedback_ready is True
    assert result.operational_evidence_ready is True
    assert result.human_evidence_ready is False
    assert result.ready_for_public_claim is False
    assert [action.action_id for action in result.actions] == ["HUMAN-EVIDENCE"]


def test_failures_generate_owned_engineering_actions_and_test_requirements() -> None:
    result = analyze_engineering_improvements(
        (
            _report(
                1,
                source_status=SourceRunStatus.FAILED,
                elapsed=35,
                complete=0.5,
                unknown_type=1,
                duplicate_urls=1,
                with_job=False,
            ),
        )
    )

    actions = {action.action_id: action for action in result.actions}
    assert {
        "DATA-COMPLETENESS",
        "DEDUP-LEAK",
        "EVAL-COVERAGE",
        "HUMAN-EVIDENCE",
        "JOB-CLASSIFICATION",
        "SEARCH-LATENCY",
        "SOURCE-RELIABILITY",
        "ZERO-RESULT-RUN",
    } <= actions.keys()
    assert actions["SOURCE-RELIABILITY"].area == "connectors"
    assert actions["SOURCE-RELIABILITY"].required_tests
    assert "immediate diagnosis" in actions["EVAL-COVERAGE"].recommendation
    assert result.rapid_feedback_ready is True
    assert result.operational_evidence_ready is False
    assert result.ready_for_public_claim is False


def test_no_live_run_cannot_claim_rapid_feedback_evidence() -> None:
    result = analyze_engineering_improvements(())

    assert result.rapid_feedback_ready is False
    assert result.operational_evidence_ready is False
    assert result.ready_for_public_claim is False


def test_aggregation_uses_p95_and_keeps_decisions_deterministic() -> None:
    reports = (_report(1, elapsed=2), _report(2, elapsed=4), _report(3, elapsed=20))

    first = analyze_engineering_improvements(reports)
    second = analyze_engineering_improvements(reports)

    assert first.signals.p95_search_seconds == 20
    assert [item.action_id for item in first.actions] == [
        item.action_id for item in second.actions
    ]
