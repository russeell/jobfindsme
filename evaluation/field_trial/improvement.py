"""Turn evaluation evidence into reviewable engineering decisions.

The analyzer never edits code or feature status. It converts measured signals
into proposed work, acceptance criteria, and regression-test requirements for a
human to approve through the normal Spec and Harness workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from evaluation.field_trial.live_loop import LiveSearchLoopReport
from evaluation.metrics.runner import ChineseBenchmarkReport
from jobfindsme.contracts import SourceRunStatus, StrictModel


class ActionPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class EngineeringThresholds(StrictModel):
    """Release-evidence policy; rapid feedback is available after one live run."""

    minimum_loop_runs: int = Field(default=3, ge=1)
    minimum_source_success_rate: float = Field(default=0.80, ge=0, le=1)
    maximum_p95_search_seconds: float = Field(default=30, ge=0)
    minimum_field_complete_rate: float = Field(default=0.95, ge=0, le=1)
    maximum_unknown_classification_rate: float = Field(default=0.20, ge=0, le=1)
    minimum_precision_at_10: float = Field(default=0.60, ge=0, le=1)
    minimum_ndcg_at_10: float = Field(default=0.70, ge=0, le=1)
    maximum_hard_filter_fnr: float = Field(default=0.05, ge=0, le=1)
    minimum_valid_link_rate: float = Field(default=0.90, ge=0, le=1)


class ImprovementAction(StrictModel):
    action_id: str
    priority: ActionPriority
    area: str
    signal: str
    observed: str
    target: str
    recommendation: str
    proposed_acceptance: tuple[str, ...]
    required_tests: tuple[str, ...]


class AggregateSignals(StrictModel):
    loop_runs: int = Field(ge=0)
    source_attempts: int = Field(ge=0)
    source_success_rate: float = Field(ge=0, le=1)
    p95_search_seconds: float = Field(ge=0)
    average_field_complete_rate: float = Field(ge=0, le=1)
    average_unknown_track_rate: float = Field(ge=0, le=1)
    average_unknown_employment_type_rate: float = Field(ge=0, le=1)
    duplicate_apply_urls: int = Field(ge=0)
    unexpected_result_sources: tuple[str, ...]
    zero_result_runs: int = Field(ge=0)
    total_results: int = Field(ge=0)


class EngineeringImprovementReport(StrictModel):
    schema_version: str = "1.0"
    generated_at: datetime
    input_sha256: tuple[str, ...]
    thresholds: EngineeringThresholds
    signals: AggregateSignals
    actions: tuple[ImprovementAction, ...]
    rapid_feedback_ready: bool
    operational_evidence_ready: bool
    human_evidence_ready: bool
    ready_for_public_claim: bool
    decision_policy: str = (
        "One live run may trigger rapid feedback but cannot support a public quality "
        "claim. Generated actions are proposals: a human approves the Spec change, "
        "and every fix adds a regression case plus holdout and live re-validation."
    )


def analyze_engineering_improvements(
    loop_reports: tuple[LiveSearchLoopReport, ...],
    *,
    benchmark: ChineseBenchmarkReport | None = None,
    thresholds: EngineeringThresholds | None = None,
    input_sha256: tuple[str, ...] = (),
) -> EngineeringImprovementReport:
    policy = thresholds or EngineeringThresholds()
    signals = _aggregate(loop_reports)
    actions = list(_operational_actions(signals, policy))
    actions.extend(_benchmark_actions(benchmark, policy))
    actions.sort(key=lambda item: (item.priority, item.action_id))
    operational_ready = (
        signals.loop_runs >= policy.minimum_loop_runs
        and signals.source_success_rate >= policy.minimum_source_success_rate
        and signals.p95_search_seconds <= policy.maximum_p95_search_seconds
        and signals.average_field_complete_rate >= policy.minimum_field_complete_rate
        and signals.average_unknown_track_rate
        <= policy.maximum_unknown_classification_rate
        and signals.average_unknown_employment_type_rate
        <= policy.maximum_unknown_classification_rate
        and signals.duplicate_apply_urls == 0
        and not signals.unexpected_result_sources
        and signals.zero_result_runs == 0
    )
    human_ready = bool(benchmark and benchmark.ready_for_claim)
    return EngineeringImprovementReport(
        generated_at=datetime.now(UTC),
        input_sha256=input_sha256,
        thresholds=policy,
        signals=signals,
        actions=tuple(actions),
        rapid_feedback_ready=(signals.loop_runs >= 1 and signals.source_attempts >= 1),
        operational_evidence_ready=operational_ready,
        human_evidence_ready=human_ready,
        ready_for_public_claim=operational_ready and human_ready,
    )


def read_loop_reports(paths: list[str | Path]) -> tuple[LiveSearchLoopReport, ...]:
    return tuple(
        LiveSearchLoopReport.model_validate_json(Path(path).read_text(encoding="utf-8"))
        for path in paths
    )


def write_improvement_report(
    path: str | Path,
    report: EngineeringImprovementReport,
) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def _aggregate(reports: tuple[LiveSearchLoopReport, ...]) -> AggregateSignals:
    attempts = [
        run
        for report in reports
        for run in report.diagnostics.source_runs
        if run.status is not SourceRunStatus.SKIPPED
    ]
    successes = [run for run in attempts if run.status is SourceRunStatus.SUCCESS]
    return AggregateSignals(
        loop_runs=len(reports),
        source_attempts=len(attempts),
        source_success_rate=len(successes) / len(attempts) if attempts else 0,
        p95_search_seconds=_percentile(
            [report.diagnostics.elapsed_seconds for report in reports],
            0.95,
        ),
        average_field_complete_rate=_average(
            [report.quality.required_field_complete_rate for report in reports]
        ),
        average_unknown_track_rate=_average(
            [report.quality.unknown_track_rate for report in reports]
        ),
        average_unknown_employment_type_rate=_average(
            [report.quality.unknown_employment_type_rate for report in reports]
        ),
        duplicate_apply_urls=sum(
            report.quality.duplicate_apply_urls for report in reports
        ),
        unexpected_result_sources=tuple(
            sorted(
                {
                    source
                    for report in reports
                    for source in report.quality.unexpected_result_sources
                }
            )
        ),
        zero_result_runs=sum(not report.jobs for report in reports),
        total_results=sum(len(report.jobs) for report in reports),
    )


def _operational_actions(
    signals: AggregateSignals,
    policy: EngineeringThresholds,
) -> tuple[ImprovementAction, ...]:
    actions = []
    if signals.loop_runs < policy.minimum_loop_runs:
        actions.append(
            _action(
                "EVAL-COVERAGE",
                ActionPriority.P1,
                "evaluation",
                "loop_run_count",
                str(signals.loop_runs),
                f">={policy.minimum_loop_runs}",
                (
                    "Use the current run for immediate diagnosis, then collect "
                    "independent runs before release or public quality claims."
                ),
                (
                    "Rapid feedback remains available after one valid live run.",
                    "Release evidence uses the same profile and Search Plan across "
                    "multiple independent runs.",
                ),
                ("Keep every raw Loop report and its hash.",),
            )
        )
    if signals.source_success_rate < policy.minimum_source_success_rate:
        actions.append(
            _action(
                "SOURCE-RELIABILITY",
                ActionPriority.P0,
                "connectors",
                "source_success_rate",
                f"{signals.source_success_rate:.3f}",
                f">={policy.minimum_source_success_rate:.3f}",
                (
                    "Rank failing sources by frequency; add replay fixtures, "
                    "explicit failure states, and bounded fallback before "
                    "adding sources."
                ),
                (
                    "Each maintained source has a dated successful live report.",
                    "A failed source cannot be reported as an empty success.",
                ),
                (
                    "Saved-page or response replay test per source.",
                    "Partial-success integration test across multiple sources.",
                ),
            )
        )
    if signals.p95_search_seconds > policy.maximum_p95_search_seconds:
        actions.append(
            _action(
                "SEARCH-LATENCY",
                ActionPriority.P1,
                "runtime",
                "p95_search_seconds",
                f"{signals.p95_search_seconds:.3f}",
                f"<={policy.maximum_p95_search_seconds:.3f}",
                (
                    "Use per-source budgets, cancellation, concurrency limits, "
                    "and cache fallback; optimize the slowest source first."
                ),
                ("P95 is generated from at least three comparable Loop runs.",),
                ("Timeout, cancellation, and slow-source regression tests.",),
            )
        )
    if signals.average_field_complete_rate < policy.minimum_field_complete_rate:
        actions.append(
            _action(
                "DATA-COMPLETENESS",
                ActionPriority.P0,
                "normalization",
                "required_field_complete_rate",
                f"{signals.average_field_complete_rate:.3f}",
                f">={policy.minimum_field_complete_rate:.3f}",
                (
                    "Capture bad source records, repair selectors or field mapping, "
                    "then freeze them as parser fixtures."
                ),
                ("Title, company, location, and direct job URL meet the target rate.",),
                ("One redacted real-record fixture for every repaired source.",),
            )
        )
    unknown_rate = max(
        signals.average_unknown_track_rate,
        signals.average_unknown_employment_type_rate,
    )
    if unknown_rate > policy.maximum_unknown_classification_rate:
        actions.append(
            _action(
                "JOB-CLASSIFICATION",
                ActionPriority.P1,
                "taxonomy",
                "unknown_classification_rate",
                f"{unknown_rate:.3f}",
                f"<={policy.maximum_unknown_classification_rate:.3f}",
                (
                    "Improve source-specific track/type extraction; keep unknown "
                    "explicit and exclude it from strict filters unless the "
                    "user opts in."
                ),
                (
                    "Track and employment type metrics are reported separately "
                    "by source.",
                ),
                ("Campus/social and internship/full-time source fixtures.",),
            )
        )
    if signals.duplicate_apply_urls:
        actions.append(
            _action(
                "DEDUP-LEAK",
                ActionPriority.P0,
                "deduplication",
                "duplicate_apply_urls",
                str(signals.duplicate_apply_urls),
                "0",
                (
                    "Add the leaked pair to canonicalization fixtures and repair "
                    "source-record to canonical-job linking."
                ),
                ("No duplicate direct URL appears in Top results.",),
                ("Cross-source and same-source duplicate-pair tests.",),
            )
        )
    if signals.unexpected_result_sources:
        actions.append(
            _action(
                "SOURCE-SCOPE-LEAK",
                ActionPriority.P0,
                "core",
                "unexpected_result_sources",
                ", ".join(signals.unexpected_result_sources),
                "none",
                (
                    "Restrict matching to the active source configuration and add "
                    "an upgrade-cache regression case."
                ),
                ("Removed or disabled sources cannot contribute results.",),
                ("Search Plan source replacement integration test.",),
            )
        )
    if signals.zero_result_runs:
        actions.append(
            _action(
                "ZERO-RESULT-RUN",
                ActionPriority.P1,
                "retrieval",
                "zero_result_runs",
                str(signals.zero_result_runs),
                "0",
                (
                    "Separate source failure, over-strict filtering, and true "
                    "no-match cases before changing ranking thresholds."
                ),
                (
                    "Every zero-result run records a machine-readable root-cause "
                    "category.",
                ),
                ("Source-failure, filter-empty, and genuine-empty tests.",),
            )
        )
    return tuple(actions)


def _benchmark_actions(
    benchmark: ChineseBenchmarkReport | None,
    policy: EngineeringThresholds,
) -> tuple[ImprovementAction, ...]:
    if benchmark is None or not benchmark.ready_for_claim:
        return (
            _action(
                "HUMAN-EVIDENCE",
                ActionPriority.P1,
                "evaluation",
                "human_labeled_evidence",
                "insufficient",
                "claim-ready benchmark",
                (
                    "Collect human relevance, liveness, link, duplicate, and "
                    "hard-filter labels before tuning ranking weights."
                ),
                ("At least 50 annotated jobs across at least three real days.",),
                ("Annotation schema validation and dataset hash verification.",),
            ),
        )
    actions = []
    if benchmark.precision_at_10 < policy.minimum_precision_at_10:
        actions.append(
            _action(
                "TOP10-PRECISION",
                ActionPriority.P0,
                "matching",
                "precision_at_10",
                f"{benchmark.precision_at_10:.3f}",
                f">={policy.minimum_precision_at_10:.3f}",
                (
                    "Analyze false positives by role family, then change filters "
                    "or scoring using a held-out labeled split."
                ),
                (
                    "P@10 improves on held-out labels without increasing "
                    "hard-filter errors.",
                ),
                ("False-positive fixtures and baseline comparison report.",),
            )
        )
    if benchmark.ndcg_at_10 < policy.minimum_ndcg_at_10:
        actions.append(
            _action(
                "TOP10-ORDERING",
                ActionPriority.P1,
                "ranking",
                "ndcg_at_10",
                f"{benchmark.ndcg_at_10:.3f}",
                f">={policy.minimum_ndcg_at_10:.3f}",
                (
                    "Tune role, skill, and evidence weights against a training "
                    "split; approve only if held-out ordering improves."
                ),
                ("NDCG@10 improves on the held-out split.",),
                ("Weight-ablation and regression report.",),
            )
        )
    if benchmark.hard_filter_fnr > policy.maximum_hard_filter_fnr:
        actions.append(
            _action(
                "HARD-FILTER-ERROR",
                ActionPriority.P0,
                "filters",
                "hard_filter_fnr",
                f"{benchmark.hard_filter_fnr:.3f}",
                f"<={policy.maximum_hard_filter_fnr:.3f}",
                (
                    "Repair the responsible salary, location, experience, track, "
                    "or type parser before adjusting rank scores."
                ),
                ("Every filter error has a typed root cause and regression fixture.",),
                ("Hard-filter confusion matrix and boundary cases.",),
            )
        )
    if benchmark.valid_link_rate < policy.minimum_valid_link_rate:
        actions.append(
            _action(
                "LINK-LIVENESS",
                ActionPriority.P0,
                "liveness",
                "valid_link_rate",
                f"{benchmark.valid_link_rate:.3f}",
                f">={policy.minimum_valid_link_rate:.3f}",
                (
                    "Prioritize canonical direct links and liveness checks; never "
                    "compensate for invalid links with ranking changes."
                ),
                ("Invalid and expired links are excluded or clearly marked.",),
                ("Redirect, closed-page, and stale-cache tests.",),
            )
        )
    return tuple(actions)


def _action(
    action_id: str,
    priority: ActionPriority,
    area: str,
    signal: str,
    observed: str,
    target: str,
    recommendation: str,
    acceptance: tuple[str, ...],
    tests: tuple[str, ...],
) -> ImprovementAction:
    return ImprovementAction(
        action_id=action_id,
        priority=priority,
        area=area,
        signal=signal,
        observed=observed,
        target=target,
        recommendation=recommendation,
        proposed_acceptance=acceptance,
        required_tests=tests,
    )


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return ordered[index]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Loop and benchmark evidence into engineering proposals."
    )
    parser.add_argument("--loop-report", type=Path, action="append", required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reports = read_loop_reports(args.loop_report)
    benchmark = (
        ChineseBenchmarkReport.model_validate_json(
            args.benchmark.read_text(encoding="utf-8")
        )
        if args.benchmark
        else None
    )
    inputs = tuple(args.loop_report) + ((args.benchmark,) if args.benchmark else ())
    report = analyze_engineering_improvements(
        reports,
        benchmark=benchmark,
        input_sha256=tuple(_sha256(path) for path in inputs),
    )
    write_improvement_report(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "actions": len(report.actions),
                "ready_for_public_claim": report.ready_for_public_claim,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
