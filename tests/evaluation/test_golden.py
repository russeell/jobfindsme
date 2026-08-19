from __future__ import annotations

from pathlib import Path

from evaluation.metrics.golden_runner import evaluate_golden_dataset

DATASET = (
    Path(__file__).parents[2] / "evaluation" / "data" / "golden" / "golden_v1.json"
)


def test_golden_regression_gate_passes() -> None:
    report = evaluate_golden_dataset(DATASET)

    assert report.gate_passed
    assert report.total_jobs == 40
    assert report.relevant_count == 24
    assert report.precision_at_k >= 0.80
    assert report.recall_at_k >= 0.80
    assert report.filter_false_negative_rate <= 0.05
    assert report.false_positive_count == 0


def test_golden_dataset_is_deterministic() -> None:
    first = evaluate_golden_dataset(DATASET)
    second = evaluate_golden_dataset(DATASET)

    assert first.recall_at_k == second.recall_at_k
    assert first.precision_at_k == second.precision_at_k
    assert first.dataset_sha256 == second.dataset_sha256
