from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import Field

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    JobLiveness,
    SearchPlan,
    SourceKind,
    StrictModel,
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
