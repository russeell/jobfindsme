from __future__ import annotations

import json

from jobfindsme.evaluation.datasets.builder import build_dataset, write_dataset
from jobfindsme.evaluation.metrics.runner import evaluate_dataset


def test_versioned_dataset_has_120_balanced_cases() -> None:
    dataset = build_dataset()
    kinds = [case["kind"] for case in dataset["cases"]]

    assert dataset["dataset_version"] == "0.1.0"
    assert dataset["dataset_type"] == "synthetic_regression"
    assert len(kinds) == 120
    assert {kind: kinds.count(kind) for kind in set(kinds)} == {
        "matching": 40,
        "freshness": 40,
        "deduplication": 40,
    }


def test_evaluation_is_reproducible_and_passes_release_gate(tmp_path) -> None:
    dataset_path = tmp_path / "eval.json"
    write_dataset(dataset_path)

    first = evaluate_dataset(dataset_path)
    second = evaluate_dataset(dataset_path)

    assert first.dataset_sha256 == second.dataset_sha256
    assert first.metrics == second.metrics
    assert first.overall_accuracy == 1
    assert first.gate_passed is True
    assert first.failed_case_ids == ()


def test_a_bad_case_is_reported_by_stable_case_id(tmp_path) -> None:
    dataset = build_dataset()
    dataset["cases"][0]["expected_match"] = not dataset["cases"][0]["expected_match"]
    path = tmp_path / "badcase.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    report = evaluate_dataset(path)

    assert "match-000" in report.failed_case_ids
    assert report.metrics["matching"].accuracy < 1
