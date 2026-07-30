from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    JobLiveness,
    SearchPlan,
    SourceKind,
    StrictModel,
)
from jobfindsme.evaluation.labeling import (
    LabeledDataset,
    compute_hard_filter_fnr,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_valid_link_rate,
)
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.matching import DeterministicMatcher


class MetricResult(StrictModel):
    passed: int
    total: int
    accuracy: float = Field(ge=0, le=1)


class EvaluationReport(StrictModel):
    dataset_version: str
    dataset_type: str
    dataset_sha256: str
    generated_at: datetime
    metrics: dict[str, MetricResult]
    overall_accuracy: float = Field(ge=0, le=1)
    gate_passed: bool
    failed_case_ids: tuple[str, ...]


def _raw_job(case_id: str, candidate: dict[str, Any]) -> RawJobRecord:
    return RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name="evaluation-fixture",
        source_url=f"https://example.com/{case_id}",
        external_id=case_id,
        payload={
            "title": candidate["title"],
            "company": "评测公司",
            "description": candidate["description"],
            "location": candidate["location"],
            "url": f"https://example.com/{case_id}",
            "published_at": "2026-07-27T00:00:00Z",
        },
    )


def _evaluate_matching(case: dict[str, Any]) -> bool:
    now = datetime(2026, 7, 28, tzinfo=UTC)
    config = case["plan"]
    plan = SearchPlan(
        plan_id=case["case_id"],
        workspace_id="evaluation",
        name="evaluation",
        target_roles=(config["role"],),
        locations=(config["location"],),
        salary_min_k=config["salary_min_k"],
        experience_max_years=config["experience_max_years"],
        exclusions=("外包", "驻场"),
        created_at=now,
        updated_at=now,
    )
    job = normalize_job(
        _raw_job(case["case_id"], case["candidate"]),
        fetched_at=now,
    )
    actual = bool(DeterministicMatcher().match(plan, [job]))
    return actual is case["expected_match"]


def _evaluate_freshness(case: dict[str, Any]) -> bool:
    now = datetime(2026, 7, 28, tzinfo=UTC)
    published_at = now - timedelta(days=case["age_days"])
    raw = RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name="evaluation-fixture",
        source_url="https://example.com/jobs",
        external_id=case["case_id"],
        payload={
            "title": "AI工程师",
            "company": "评测公司",
            "url": "https://example.com/jobs/1",
            "published_at": published_at.isoformat(),
            "closed": case["closed"],
        },
    )
    actual = normalize_job(raw, fetched_at=now).source.liveness
    return actual == JobLiveness(case["expected"])


def _evaluate_deduplication(case: dict[str, Any]) -> bool:
    base = ("公司", "AI工程师", "https://example.com/jobs/1")
    other = (
        base[0] if case["same_company"] else "另一公司",
        base[1] if case["same_title"] else "后端工程师",
        base[2] if case["same_url"] else "https://example.com/jobs/2",
    )
    left = hashlib.sha256("|".join(base).encode()).hexdigest()
    right = hashlib.sha256("|".join(other).encode()).hexdigest()
    return (left == right) is case["expected_duplicate"]


def evaluate_dataset(path: str | Path) -> EvaluationReport:
    dataset_path = Path(path)
    raw_bytes = dataset_path.read_bytes()
    dataset = json.loads(raw_bytes)
    evaluators = {
        "matching": _evaluate_matching,
        "freshness": _evaluate_freshness,
        "deduplication": _evaluate_deduplication,
    }
    counts: dict[str, list[int]] = {name: [0, 0] for name in evaluators}
    failures = []
    for case in dataset["cases"]:
        kind = case["kind"]
        passed = evaluators[kind](case)
        counts[kind][1] += 1
        counts[kind][0] += int(passed)
        if not passed:
            failures.append(case["case_id"])
    metrics = {
        name: MetricResult(
            passed=passed,
            total=total,
            accuracy=passed / total if total else 0,
        )
        for name, (passed, total) in counts.items()
    }
    total = sum(metric.total for metric in metrics.values())
    passed = sum(metric.passed for metric in metrics.values())
    overall = passed / total if total else 0
    return EvaluationReport(
        dataset_version=dataset["dataset_version"],
        dataset_type=dataset["dataset_type"],
        dataset_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        generated_at=datetime.now(UTC),
        metrics=metrics,
        overall_accuracy=overall,
        gate_passed=all(metric.accuracy >= 0.95 for metric in metrics.values()),
        failed_case_ids=tuple(failures),
    )


class ChineseBenchmarkReport(StrictModel):
    """Metrics for a real Chinese labeled dataset (M14-001)."""

    dataset_version: str
    dataset_sha256: str
    generated_at: datetime
    total_labeled: int
    total_unlabeled: int
    total_days: int
    precision_at_10: float = Field(ge=0, le=1)
    ndcg_at_10: float = Field(ge=0, le=1)
    hard_filter_fnr: float = Field(ge=0, le=1)
    valid_link_rate: float = Field(ge=0, le=1)
    source_success_rate: float = Field(ge=0, le=1)
    source_failure_sources: tuple[str, ...]
    duplicates_detected: int = 0
    duplicate_leaks: int = 0
    evidence_kind: str
    provenance_verified: bool
    provenance_issues: tuple[str, ...] = ()
    ready_for_claim: bool
    synthetic_metrics: EvaluationReport | None = None

    def summary(self) -> str:
        return (
            f"M14 Chinese Benchmark v{self.dataset_version}\n"
            f"  Labeled: {self.total_labeled} jobs over {self.total_days} days "
            f"({self.total_unlabeled} pending)\n"
            f"  P@10:     {self.precision_at_10:.3f}\n"
            f"  NDCG@10:  {self.ndcg_at_10:.3f}\n"
            f"  FNR:      {self.hard_filter_fnr:.3f}\n"
            f"  ValidLink:{self.valid_link_rate:.3f}\n"
            f"  SourceOK: {self.source_success_rate:.3f}\n"
            f"  Deduped:  {self.duplicates_detected}\n"
            f"  DupLeaks: {self.duplicate_leaks}\n"
            f"  Evidence: {self.evidence_kind} "
            f"(verified={self.provenance_verified})\n"
            f"  Claimable:{self.ready_for_claim}\n"
            f"  SrcFail:  {', '.join(self.source_failure_sources) or 'none'}"
        )


def evaluate_chinese_dataset(path: str | Path) -> ChineseBenchmarkReport:
    """Evaluate a real Chinese labeled dataset."""
    dataset_path = Path(path)
    raw_bytes = dataset_path.read_bytes()
    data = json.loads(raw_bytes)
    dataset = LabeledDataset.model_validate(data)

    all_candidates = list(dataset.all_labels)
    all_labels = [label for label in all_candidates if label.annotated]
    source_failures: set[str] = set()
    source_attempts: set[tuple[int, str]] = set()
    source_successes: set[tuple[int, str]] = set()
    for day in dataset.days:
        source_failures.update(day.source_failures)
        source_attempts.update((day.day, source) for source in day.source_attempts)
        source_successes.update((day.day, source) for source in day.source_successes)

    duplicate_leaks = sum(1 for label in all_labels if label.duplicate_of is not None)
    duplicates_detected = sum(day.duplicates_detected for day in dataset.days)
    evaluated_days = [
        [label for label in day.labels if label.annotated] for day in dataset.days
    ]
    evaluated_days = [labels for labels in evaluated_days if labels]
    precision_at_10 = (
        sum(compute_precision_at_k(labels, 10) for labels in evaluated_days)
        / len(evaluated_days)
        if evaluated_days
        else 0.0
    )
    ndcg_at_10 = (
        sum(compute_ndcg_at_k(labels, 10) for labels in evaluated_days)
        / len(evaluated_days)
        if evaluated_days
        else 0.0
    )
    source_success_rate = (
        len(source_successes) / len(source_attempts) if source_attempts else 0.0
    )
    total_unlabeled = len(all_candidates) - len(all_labels)
    provenance_verified, provenance_issues = _verify_field_provenance(dataset)
    ready_for_claim = (
        len(all_labels) >= 50
        and len(evaluated_days) >= 3
        and total_unlabeled == 0
        and provenance_verified
    )

    return ChineseBenchmarkReport(
        dataset_version=dataset.dataset_version,
        dataset_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        generated_at=datetime.now(UTC),
        total_labeled=len(all_labels),
        total_unlabeled=total_unlabeled,
        total_days=len(dataset.days),
        precision_at_10=precision_at_10,
        ndcg_at_10=ndcg_at_10,
        hard_filter_fnr=compute_hard_filter_fnr(all_labels),
        valid_link_rate=compute_valid_link_rate(all_labels),
        source_success_rate=source_success_rate,
        source_failure_sources=tuple(sorted(source_failures)),
        duplicates_detected=duplicates_detected,
        duplicate_leaks=duplicate_leaks,
        evidence_kind=dataset.provenance.evidence_kind,
        provenance_verified=provenance_verified,
        provenance_issues=provenance_issues,
        ready_for_claim=ready_for_claim,
    )


def _verify_field_provenance(
    dataset: LabeledDataset,
) -> tuple[bool, tuple[str, ...]]:
    from jobfindsme.evaluation.live_loop import LiveSearchLoopReport

    provenance = dataset.provenance
    issues = []
    if provenance.evidence_kind != "field_trial":
        issues.append("dataset is not declared as field_trial evidence")
    if provenance.collection_method != "live_loop_human_annotation":
        issues.append("collection method is not live_loop_human_annotation")
    if not provenance.human_annotated:
        issues.append("human annotation is not attested")
    if not provenance.labeler:
        issues.append("labeler is missing")
    if len(provenance.source_report_paths) != len(dataset.days):
        issues.append("each labeled day must have exactly one source Loop report")

    run_ids = set()
    for index, raw_path in enumerate(provenance.source_report_paths):
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        expected = provenance.source_report_sha256.get(raw_path)
        if not path.is_file():
            issues.append(f"source report missing: {raw_path}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not expected:
            issues.append(f"source report hash missing: {raw_path}")
        elif actual != expected:
            issues.append(f"source report hash mismatch: {raw_path}")
        try:
            report = LiveSearchLoopReport.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError):
            issues.append(f"invalid Live Loop report: {raw_path}")
            continue
        if report.run_id in run_ids:
            issues.append(f"duplicate Live Loop run_id: {report.run_id}")
        run_ids.add(report.run_id)
        if index >= len(dataset.days):
            continue
        day = dataset.days[index]
        if report.plan_id != day.plan_id:
            issues.append(f"plan_id mismatch: {raw_path}")
        if report.profile_hash != day.profile_hash:
            issues.append(f"profile_hash mismatch: {raw_path}")
        if tuple(job.job_id for job in report.jobs[: len(day.labels)]) != tuple(
            label.job_id for label in day.labels
        ):
            issues.append(f"Top job IDs mismatch: {raw_path}")

    return not issues, tuple(issues)
