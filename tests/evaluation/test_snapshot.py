"""Tests for L1–L4 evaluation tools: snapshot, compare, diff."""

from pathlib import Path

from jobfindsme.contracts import (
    JobLiveness,
    JobPosting,
    SearchPlan,
    SourceEvidence,
    SourceKind,
)
from jobfindsme.evaluation.snapshot import (
    compare_results,
    diff_loop_reports,
    load_job_snapshot,
    replay_snapshot,
    save_job_snapshot,
)
from jobfindsme.matching import DeterministicMatcher


def _make_job(job_id: str, title: str, description: str = "") -> JobPosting:
    from datetime import UTC, datetime

    from jobfindsme.contracts import EmploymentType, RecruitmentTrack

    now = datetime(2026, 7, 30, tzinfo=UTC)
    return JobPosting(
        job_id=job_id,
        fingerprint=f"fp_{job_id}_padding_to_16",
        content_hash=f"hash_{job_id}_pad16chars",
        title=title,
        company="测试公司",
        description=description or f"岗位描述 {title} Python RAG Agent",
        locations=("上海",),
        source=SourceEvidence(
            source_kind=SourceKind.CAREER_SITE,
            source_name="BOSS直聘",
            source_url="https://example.com",
            liveness=JobLiveness.ACTIVE,
            fetched_at=now,
        ),
        salary_min_k=20,
        salary_max_k=40,
        recruitment_track=RecruitmentTrack.SOCIAL,
        employment_type=EmploymentType.FULL_TIME,
        apply_url=f"https://example.com/{job_id}",
        external_id=job_id,
    )


# ── L1: Snapshot save / load / replay ────────────────────────────────────────


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    jobs = [
        _make_job("j1", "AI应用工程师"),
        _make_job("j2", "大模型算法工程师"),
        _make_job("j3", "后端工程师"),
    ]
    path = tmp_path / "snapshot.json"
    save_job_snapshot(jobs, path)
    snapshot = load_job_snapshot(path)
    assert snapshot is not None
    assert len(snapshot.jobs) == 3
    assert snapshot.jobs[0].title == "AI应用工程师"


def test_replay_snapshot_applies_current_matcher(tmp_path: Path) -> None:
    jobs = [
        _make_job("j1", "AI应用工程师", "Python RAG Agent 大模型"),
        _make_job("j2", "销售经理", "客户开发 商务谈判"),
        _make_job("j3", "Python AI开发", "Python FastAPI RAG"),
    ]
    path = tmp_path / "snapshot.json"
    save_job_snapshot(jobs, path)
    snapshot = load_job_snapshot(path)

    from datetime import UTC, datetime

    plan = SearchPlan(
        plan_id="plan_test",
        workspace_id="ws_test",
        name="test",
        target_roles=("AI应用工程师",),
        locations=("上海",),
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        updated_at=datetime(2026, 7, 30, tzinfo=UTC),
    )
    result = replay_snapshot(snapshot, plan)
    # j1 and j3 should pass, j2 should be filtered
    assert result.passed_filter >= 1
    titles = {m.job.title for m in result.matches}
    assert "销售经理" not in titles


def test_replay_snapshot_score_is_deterministic(tmp_path: Path) -> None:
    jobs = [_make_job("j1", "AI应用工程师", "Python RAG Agent 大模型")]
    path = tmp_path / "snapshot.json"
    save_job_snapshot(jobs, path)
    snapshot = load_job_snapshot(path)

    from datetime import UTC, datetime

    plan = SearchPlan(
        plan_id="plan_test",
        workspace_id="ws_test",
        name="test",
        target_roles=("AI应用工程师",),
        locations=("上海",),
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        updated_at=datetime(2026, 7, 30, tzinfo=UTC),
    )
    r1 = replay_snapshot(snapshot, plan)
    r2 = replay_snapshot(snapshot, plan)
    assert r1.passed_filter == r2.passed_filter
    for a, b in zip(r1.matches, r2.matches, strict=True):
        assert a.score == b.score


# ── L3: Pairwise comparator ──────────────────────────────────────────────────


def test_compare_identical_results(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    jobs = [
        _make_job("j1", "AI应用工程师"),
        _make_job("j2", "大模型算法"),
    ]
    plan = SearchPlan(
        plan_id="p1",
        workspace_id="w1",
        name="t",
        target_roles=("AI应用工程师",),
        locations=(),
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        updated_at=datetime(2026, 7, 30, tzinfo=UTC),
    )
    matcher = DeterministicMatcher()
    matches = matcher.match(plan, jobs)
    report = compare_results(matches, matches)
    assert report.unchanged == len(matches)
    assert report.new_jobs == 0
    assert report.removed_jobs == 0
    assert report.score_improved == 0
    assert report.score_declined == 0


def test_compare_detects_new_and_removed(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    all_jobs = [
        _make_job("j1", "AI应用工程师", "Python RAG Agent 大模型 LLM 应用"),
        _make_job("j2", "AI应用工程师（Agent方向）", "LangChain Agent 智能体"),
        _make_job("j3", "大模型应用开发", "RAG LangChain LLM 大模型应用"),
    ]
    plan = SearchPlan(
        plan_id="p1",
        workspace_id="w1",
        name="t",
        target_roles=("AI应用工程师",),
        locations=(),
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
        updated_at=datetime(2026, 7, 30, tzinfo=UTC),
    )
    matcher = DeterministicMatcher()
    baseline = matcher.match(plan, all_jobs[:2])  # j1, j2
    candidate = matcher.match(plan, all_jobs[1:])  # j2, j3
    report = compare_results(baseline, candidate)
    # j1 removed, j2 present in both, j3 may or may not pass filter
    assert report.removed_jobs >= 1
    assert report.unchanged + report.score_improved + report.score_declined >= 1


# ── L4: Time-window differ ───────────────────────────────────────────────────


def _write_loop_report(path: Path, run_id: str, jobs: list[dict]) -> None:
    import json

    report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "agent_host": "test",
        "workspace_id": "ws1",
        "plan_id": "plan1",
        "profile_hash": "abc",
        "generated_at": "2026-07-30T00:00:00Z",
        "diagnostics": {
            "started_at": "2026-07-30T00:00:00Z",
            "finished_at": "2026-07-30T00:00:01Z",
            "elapsed_seconds": 1.0,
            "matching_seconds": 0.1,
            "source_runs": [],
            "total_discovered": len(jobs),
            "total_unique": len(jobs),
            "duplicates_removed": 0,
            "result_count": len(jobs),
        },
        "quality": {
            "source_success_rate": 1.0,
            "url_shape_valid_rate": 1.0,
            "required_field_complete_rate": 1.0,
            "unknown_track_rate": 0.0,
            "unknown_employment_type_rate": 0.0,
            "duplicate_apply_urls": 0,
            "average_match_score": 0.5,
            "unexpected_result_sources": [],
            "automatic_findings": [],
        },
        "jobs": jobs,
        "claim_boundary": "test",
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def test_diff_detects_new_and_closed_jobs(tmp_path: Path) -> None:
    day1 = tmp_path / "day1.json"
    day2 = tmp_path / "day2.json"
    _write_loop_report(
        day1,
        "run1",
        [
            {
                "rank": 1,
                "job_id": "j1",
                "source_name": "BOSS直聘",
                "title": "AI应用工程师",
                "company": "A",
                "location": "上海",
                "score": 0.5,
                "recruitment_track": "social",
                "employment_type": "full_time",
                "apply_url": "https://x.com/1",
            },
            {
                "rank": 2,
                "job_id": "j2",
                "source_name": "BOSS直聘",
                "title": "后端工程师",
                "company": "B",
                "location": "上海",
                "score": 0.3,
                "recruitment_track": "social",
                "employment_type": "full_time",
                "apply_url": "https://x.com/2",
            },
        ],
    )
    _write_loop_report(
        day2,
        "run2",
        [
            {
                "rank": 1,
                "job_id": "j2",
                "source_name": "BOSS直聘",
                "title": "后端工程师",
                "company": "B",
                "location": "上海",
                "score": 0.35,
                "recruitment_track": "social",
                "employment_type": "full_time",
                "apply_url": "https://x.com/2",
            },
            {
                "rank": 2,
                "job_id": "j3",
                "source_name": "BOSS直聘",
                "title": "大模型工程师",
                "company": "C",
                "location": "上海",
                "score": 0.45,
                "recruitment_track": "social",
                "employment_type": "full_time",
                "apply_url": "https://x.com/3",
            },
        ],
    )
    report = diff_loop_reports(day1, day2)
    assert report.new_jobs == 1  # j3
    assert report.closed_jobs >= 1  # j1 closed
    assert report.changed_jobs >= 1  # j2 score changed


def test_diff_identical_reports_are_all_unchanged(tmp_path: Path) -> None:
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    jobs = [
        {
            "rank": 1,
            "job_id": "j1",
            "source_name": "BOSS直聘",
            "title": "AI应用工程师",
            "company": "A",
            "location": "上海",
            "score": 0.5,
            "recruitment_track": "social",
            "employment_type": "full_time",
            "apply_url": "https://x.com/1",
        }
    ]
    _write_loop_report(path_a, "run_a", jobs)
    _write_loop_report(path_b, "run_b", jobs)
    report = diff_loop_reports(path_a, path_b)
    assert report.new_jobs == 0
    assert report.closed_jobs == 0
    assert report.unchanged_jobs == 1
