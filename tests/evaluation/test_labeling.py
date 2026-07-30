"""Tests for labeling models and Chinese benchmark evaluation."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from jobfindsme.contracts import SearchRunDiagnostics
from jobfindsme.evaluation.labeling import (
    JobLabel,
    assemble_labeled_dataset,
    compute_hard_filter_fnr,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_valid_link_rate,
    new_daily_template,
    write_daily_template,
)
from jobfindsme.evaluation.live_loop import (
    LiveSearchLoopReport,
    LoopJob,
    LoopQuality,
)
from jobfindsme.evaluation.runner import evaluate_chinese_dataset

# ── Fixtures ─────────────────────────────────────────────────────────────────


def _sample_jobs(n: int = 8) -> list[dict]:
    return [
        {
            "job_id": f"job-{i:03}",
            "source_name": "baidu" if i % 2 else "boss_cdp",
            "apply_url": f"https://example.com/jobs/{i}",
            "title": "AI应用工程师" if i < 5 else "前端工程师",
            "company": f"公司{i}",
            "location": "杭州" if i < 4 else "北京",
        }
        for i in range(n)
    ]


def _make_labels(
    relevance: list[int],
    hard_filter: list[int] | None = None,
    valid_link: list[int] | None = None,
) -> tuple[JobLabel, ...]:
    labels = []
    for i, rel in enumerate(relevance):
        labels.append(
            JobLabel(
                rank=i + 1,
                job_id=f"job-{i:03}",
                source_name="test",
                apply_url=f"https://example.com/{i}",
                title=f"岗位{i}",
                company=f"公司{i}",
                location="杭州",
                relevance=rel,
                hard_filter_error=bool(hard_filter[i]) if hard_filter else False,
                valid_link=bool(valid_link[i]) if valid_link else True,
            )
        )
    return tuple(labels)


# ── Daily template ───────────────────────────────────────────────────────────


def test_new_daily_template_creates_correct_structure() -> None:
    jobs = _sample_jobs(8)
    template = new_daily_template(
        day=1,
        date="2026-07-28",
        plan_id="plan-1",
        profile_hash="abc123",
        jobs=jobs,
    )

    assert template.day == 1
    assert len(template.labels) == 8
    assert template.labels[0].rank == 1
    assert template.labels[7].rank == 8
    assert template.labels[0].job_id == "job-000"
    assert template.total_discovered == 8
    assert template.total_after_filter == 8


def test_daily_template_rejects_success_for_unattempted_source() -> None:
    with pytest.raises(ValueError, match="source_successes"):
        new_daily_template(
            day=1,
            date="2026-07-28",
            plan_id="plan-1",
            profile_hash="abc123",
            jobs=_sample_jobs(1),
            source_attempts=["baidu"],
            source_successes=["bytedance"],
        )


def test_daily_template_roundtrip(tmp_path) -> None:
    jobs = _sample_jobs(5)
    template = new_daily_template(
        day=1,
        date="2026-07-28",
        plan_id="plan-1",
        profile_hash="abc123",
        jobs=jobs,
    )
    path = tmp_path / "day_01.json"
    write_daily_template(path, template)

    # Modify manually (simulating human annotation)
    data = json.loads(path.read_text())
    data["labels"][0]["relevance"] = 3
    data["labels"][1]["relevance"] = 2
    data["labels"][0]["valid_link"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Read back
    from jobfindsme.evaluation.labeling import read_daily_labels

    loaded = read_daily_labels(path)
    assert loaded.labels[0].relevance == 3
    assert loaded.labels[1].relevance == 2


# ── Metrics ──────────────────────────────────────────────────────────────────


def test_precision_at_k_all_relevant() -> None:
    labels = list(_make_labels([3, 3, 2, 2, 2, 1, 1, 0, 0, 0]))
    assert compute_precision_at_k(labels, 5) == 1.0  # All >= 2
    assert compute_precision_at_k(labels, 10) == 0.5  # 5 out of 10 >= 2


def test_precision_at_k_none_relevant() -> None:
    labels = list(_make_labels([0, 0, 0, 0, 0]))
    assert compute_precision_at_k(labels, 5) == 0.0


def test_ndcg_at_k_perfect_ordering() -> None:
    """Perfectly ordered (descending relevance)."""
    labels = list(_make_labels([3, 3, 2, 2, 1, 1, 0, 0]))
    ndcg = compute_ndcg_at_k(labels, 8)
    assert ndcg == 1.0


def test_ndcg_at_k_poor_ordering() -> None:
    """Poor ordering: low relevance first."""
    labels = list(_make_labels([0, 0, 1, 1, 2, 2, 3, 3]))
    ndcg = compute_ndcg_at_k(labels, 8)
    assert ndcg < 0.7  # Well below perfect


def test_ndcg_at_k_empty() -> None:
    assert compute_ndcg_at_k([], 10) == 0.0


def test_hard_filter_fnr() -> None:
    labels = list(
        _make_labels(
            [2, 2, 2, 2, 1],
            hard_filter=[0, 0, 1, 0, 0],
        )
    )
    assert compute_hard_filter_fnr(labels) == 0.2


def test_valid_link_rate() -> None:
    labels = list(
        _make_labels(
            [2, 2, 2, 2, 2],
            valid_link=[1, 1, 0, 1, 1],
        )
    )
    assert compute_valid_link_rate(labels) == 0.8


# ── Dataset assembly ─────────────────────────────────────────────────────────


def test_assemble_labeled_dataset(tmp_path) -> None:
    # Create two daily label files
    for day in (1, 2):
        jobs = _sample_jobs(5)
        template = new_daily_template(
            day=day,
            date=f"2026-07-2{day}",
            plan_id="plan-1",
            profile_hash="abc123",
            jobs=jobs,
        )
        path = tmp_path / f"day_0{day}.json"
        write_daily_template(path, template)

        # Annotate
        data = json.loads(path.read_text())
        for lb in data["labels"]:
            lb["annotated"] = True
            lb["relevance"] = 2
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    dataset = assemble_labeled_dataset(
        version="0.2.0",
        provenance={"labeler": "test", "date_range": "2026-07-21 to 2026-07-27"},
        day_paths=[tmp_path / "day_01.json", tmp_path / "day_02.json"],
    )

    assert dataset.dataset_version == "0.2.0"
    assert len(dataset.days) == 2
    assert len(dataset.all_labels) == 10


# ── Chinese benchmark evaluation ─────────────────────────────────────────────


def test_evaluate_chinese_dataset(tmp_path) -> None:
    # Build a complete labeled dataset
    for day in (1, 2):
        jobs = _sample_jobs(5)
        template = new_daily_template(
            day=day,
            date=f"2026-07-2{day}",
            plan_id="plan-1",
            profile_hash="abc123",
            jobs=jobs,
            source_failures=["boss"] if day == 1 else [],
        )
        path = tmp_path / f"day_0{day}.json"
        write_daily_template(path, template)

        data = json.loads(path.read_text())
        for i, lb in enumerate(data["labels"]):
            lb["annotated"] = True
            lb["relevance"] = 3 if i < 3 else 2
            lb["valid_link"] = i != 4
        data["source_attempts"] = ["baidu", "bytedance"]
        data["source_successes"] = ["baidu", "bytedance"] if day == 2 else ["baidu"]
        data["duplicates_detected"] = day
        data["labels"][0]["duplicate_of"] = None
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Assemble
    dataset = assemble_labeled_dataset(
        version="0.2.0",
        provenance={"labeler": "test"},
        day_paths=[tmp_path / "day_01.json", tmp_path / "day_02.json"],
    )

    from jobfindsme.evaluation.labeling import write_labeled_dataset

    dataset_path = tmp_path / "labeled.json"
    write_labeled_dataset(dataset_path, dataset)

    # Evaluate
    report = evaluate_chinese_dataset(dataset_path)

    assert report.total_labeled == 10
    assert report.total_unlabeled == 0
    assert report.total_days == 2
    assert report.precision_at_10 == 1.0  # All >= 2
    assert report.ndcg_at_10 >= 0.9  # Good ordering
    assert report.hard_filter_fnr == 0.0
    assert report.valid_link_rate == 0.8  # 2 out of 10 invalid (one per day)
    assert report.source_success_rate == 0.75
    assert report.duplicates_detected == 3
    assert report.duplicate_leaks == 0
    assert report.ready_for_claim is False
    assert "boss" in report.source_failure_sources
    assert "M14 Chinese Benchmark" in report.summary()


def test_chinese_metrics_macro_average_each_day(tmp_path) -> None:
    """A poor second day must affect P@10 and NDCG@10."""
    paths = []
    for day, relevances in ((1, [3] * 10), (2, [0] * 10)):
        template = new_daily_template(
            day=day,
            date=f"2026-07-{27 + day}",
            plan_id="plan-1",
            profile_hash="abc123",
            jobs=_sample_jobs(10),
        )
        path = tmp_path / f"day_{day:02}.json"
        write_daily_template(path, template)
        data = json.loads(path.read_text())
        for label, relevance in zip(data["labels"], relevances, strict=True):
            label["annotated"] = True
            label["relevance"] = relevance
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        paths.append(path)

    dataset = assemble_labeled_dataset(
        version="0.2.0",
        provenance={"labeler": "test"},
        day_paths=paths,
    )
    from jobfindsme.evaluation.labeling import write_labeled_dataset

    dataset_path = tmp_path / "macro.json"
    write_labeled_dataset(dataset_path, dataset)
    report = evaluate_chinese_dataset(dataset_path)

    assert report.precision_at_10 == 0.5
    assert report.ndcg_at_10 == 0.5


def test_unannotated_template_is_not_counted_as_human_evidence(tmp_path) -> None:
    path = tmp_path / "day_01.json"
    write_daily_template(
        path,
        new_daily_template(
            day=1,
            date="2026-07-28",
            plan_id="plan-1",
            profile_hash="abc123",
            jobs=_sample_jobs(5),
        ),
    )
    dataset = assemble_labeled_dataset(
        version="0.2.0",
        provenance={"labeler": "pending"},
        day_paths=[path],
    )
    from jobfindsme.evaluation.labeling import write_labeled_dataset

    dataset_path = tmp_path / "pending.json"
    write_labeled_dataset(dataset_path, dataset)
    report = evaluate_chinese_dataset(dataset_path)

    assert report.total_labeled == 0
    assert report.total_unlabeled == 5
    assert report.ready_for_claim is False


def _build_claim_sized_dataset(tmp_path, provenance: dict) -> tuple[object, list]:
    day_paths = []
    for day in range(1, 6):
        path = tmp_path / f"day_{day:02}.json"
        template = new_daily_template(
            day=day,
            date=f"2026-07-{24 + day}",
            plan_id="plan-1",
            profile_hash="profile-hash",
            jobs=_sample_jobs(10),
        )
        write_daily_template(path, template)
        data = json.loads(path.read_text())
        for label in data["labels"]:
            label["annotated"] = True
            label["relevance"] = 2
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        day_paths.append(path)
    return (
        assemble_labeled_dataset(
            version="1.0.0",
            provenance=provenance,
            day_paths=day_paths,
        ),
        day_paths,
    )


def test_synthetic_50_job_dataset_is_never_claim_ready(tmp_path) -> None:
    dataset, _ = _build_claim_sized_dataset(
        tmp_path,
        {
            "evidence_kind": "synthetic",
            "collection_method": "generated_fixture",
            "labeler": "builder-script",
        },
    )
    from jobfindsme.evaluation.labeling import write_labeled_dataset

    dataset_path = tmp_path / "synthetic.json"
    write_labeled_dataset(dataset_path, dataset)
    report = evaluate_chinese_dataset(dataset_path)

    assert report.total_labeled == 50
    assert report.evidence_kind == "synthetic"
    assert report.provenance_verified is False
    assert report.ready_for_claim is False


def test_field_claim_requires_hashed_live_loop_reports(tmp_path) -> None:
    initial, day_paths = _build_claim_sized_dataset(
        tmp_path,
        {"evidence_kind": "synthetic"},
    )
    report_paths = []
    report_hashes = {}
    now = datetime(2026, 7, 25, tzinfo=UTC)
    for day in initial.days:
        path = tmp_path / f"loop_{day.day}.json"
        jobs = tuple(
            LoopJob(
                rank=label.rank,
                job_id=label.job_id,
                source_name=label.source_name,
                title=label.title,
                company=label.company,
                location=label.location,
                score=0.8,
                recruitment_track="unknown",
                employment_type="unknown",
                apply_url=label.apply_url,
            )
            for label in day.labels
        )
        report = LiveSearchLoopReport(
            run_id=f"run-{day.day}",
            agent_host="codex",
            workspace_id="workspace",
            plan_id=day.plan_id,
            profile_hash=day.profile_hash,
            generated_at=now + timedelta(days=day.day),
            diagnostics=SearchRunDiagnostics(
                started_at=now,
                finished_at=now,
                elapsed_seconds=0,
                matching_seconds=0,
                result_count=len(jobs),
            ),
            quality=LoopQuality(
                source_success_rate=1,
                url_shape_valid_rate=1,
                required_field_complete_rate=1,
                unknown_track_rate=1,
                unknown_employment_type_rate=1,
                duplicate_apply_urls=0,
                average_match_score=0.8,
            ),
            jobs=jobs,
        )
        path.write_text(report.model_dump_json(indent=2))
        raw_path = str(path)
        report_paths.append(raw_path)
        report_hashes[raw_path] = hashlib.sha256(path.read_bytes()).hexdigest()

    dataset = assemble_labeled_dataset(
        version="1.0.0",
        provenance={
            "evidence_kind": "field_trial",
            "collection_method": "live_loop_human_annotation",
            "human_annotated": True,
            "labeler": "owner",
            "source_report_paths": report_paths,
            "source_report_sha256": report_hashes,
        },
        day_paths=day_paths,
    )
    from jobfindsme.evaluation.labeling import write_labeled_dataset

    dataset_path = tmp_path / "field.json"
    write_labeled_dataset(dataset_path, dataset)
    report = evaluate_chinese_dataset(dataset_path)

    assert report.provenance_verified is True
    assert report.ready_for_claim is True

    Path(report_paths[0]).write_text("tampered")
    tampered = evaluate_chinese_dataset(dataset_path)
    assert tampered.provenance_verified is False
    assert tampered.ready_for_claim is False
    assert any("hash mismatch" in issue for issue in tampered.provenance_issues)
