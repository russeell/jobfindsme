"""Evaluation tooling — development-time quality gates, never production paths.

Dependency direction is one way:

    evaluation → production Core
    Core ✗→ evaluation

Layout:
    datasets/    — synthetic and field datasets, labeling templates
    metrics/     — evaluate_dataset / evaluate_chinese_dataset, reports
    regression/  — snapshot replay and the frozen legacy BM25 matcher
    field_trial/ — live loop, labeling CLI, improvement analysis
    cli.py       — evaluation entry (python -m jobfindsme.evaluation.cli)
"""

from __future__ import annotations

from jobfindsme.evaluation.metrics.runner import (
    ChineseBenchmarkReport,
    EvaluationReport,
    evaluate_chinese_dataset,
    evaluate_dataset,
)

__all__ = [
    "ChineseBenchmarkReport",
    "EvaluationReport",
    "evaluate_chinese_dataset",
    "evaluate_dataset",
]
