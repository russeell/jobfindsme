"""Golden matching regression: Precision/Recall/FNR over a labeled set.

Headline metrics are Recall@K and False-Negative rate: missing a good job is
more dangerous for a job seeker than surfacing one mediocre match.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobfindsme.app import jobfindsmecore
from jobfindsme.contracts import StrictModel
from jobfindsme.importing.parsers import parse_json


class GoldenReport(StrictModel):
    dataset_version: str
    dataset_sha256: str
    generated_at: datetime
    total_jobs: int = 0
    relevant_count: int = 0
    predicted_count: int = 0
    precision_at_k: float = 0
    recall_at_k: float = 0
    filter_false_negative_rate: float = 0
    false_positive_count: int = 0
    top_k_relevance: dict[str, int] = {}
    miss_reasons: dict[str, int] = {}
    gate_passed: bool = False

    def summary(self) -> str:
        return (
            f"Golden {self.dataset_version}\n"
            f"  Jobs: {self.total_jobs} (relevant {self.relevant_count})\n"
            f"  Precision@{20}: {self.precision_at_k:.3f}\n"
            f"  Recall@{20}:    {self.recall_at_k:.3f}\n"
            f"  Filter FNR:    {self.filter_false_negative_rate:.3f}\n"
            f"  FP:            {self.false_positive_count}\n"
            f"  Top20:         {self.top_k_relevance}\n"
            f"  Miss reasons:  {self.miss_reasons}\n"
            f"  Gate:          {'PASS' if self.gate_passed else 'FAIL'}"
        )


def _miss_reason(job: dict[str, Any], plan: dict[str, Any]) -> str:
    text = f"{job['title']} {job['description']}".casefold()
    if any(term in text for term in plan.get("exclusions", [])):
        return "exclusion"
    if "面议" in text or "15-18" in text:
        return "salary"
    cities = plan.get("locations", [])
    if cities and not any(city in text for city in cities):
        return "city"
    if "实习" in text:
        return "employment_type"
    if "校招" in text or "应届" in text:
        return "track"
    if job.get("closed"):
        return "closed"
    return "role"


def evaluate_golden_dataset(
    dataset_path: str | Path,
    *,
    core: Any = None,
    k: int = 20,
) -> GoldenReport:
    raw = Path(dataset_path).read_bytes()
    dataset = json.loads(raw)
    plan = dataset["plan"]

    if core is None:
        tmp = Path(tempfile.mkdtemp()) / "golden.db"
        core = jobfindsmecore(tmp)
    core.configure_search(
        target_role=plan["target_role"],
        locations=plan["locations"],
        salary_min_k=plan.get("salary_min_k"),
        recruitment_track=plan.get("recruitment_track"),
        employment_type=plan.get("employment_type"),
        exclusions=plan.get("exclusions", []),
    )
    workspace_id = core.context.resolve_workspace().workspace_id
    core.job_imports.import_records(
        workspace_id,
        parse_json(
            json.dumps(dataset["jobs"], ensure_ascii=False),
            source_name="黄金集",
        ),
    )

    matches = core.match_jobs(limit=len(dataset["jobs"]), use_profile=False)
    predicted = [match.job.external_id for match in matches[:k]]
    predicted_set = set(predicted)
    relevant = {job["id"] for job in dataset["jobs"] if job["label"]["should_match"]}
    relevant_set = set(relevant)

    all_predicted = {match.job.external_id for match in matches}
    hits = predicted_set & relevant_set
    # Filter misses (false negatives): relevant jobs rejected by hard filter.
    filter_misses = relevant_set - all_predicted
    false_positives = predicted_set - relevant_set
    recall = len(hits) / len(relevant_set) if relevant_set else 0.0
    precision = len(hits) / len(predicted_set) if predicted_set else 0.0
    filter_fnr = len(filter_misses) / len(relevant_set) if relevant_set else 0.0

    relevance_by_id = {job["id"]: job["label"]["relevance"] for job in dataset["jobs"]}
    top_counts = {"high": 0, "medium": 0, "low": 0}
    for job_id in predicted:
        top_counts[relevance_by_id.get(job_id, "low")] += 1

    reasons: dict[str, int] = {}
    by_id = {job["id"]: job for job in dataset["jobs"]}
    for job_id in sorted(filter_misses):
        reason = _miss_reason(by_id[job_id], plan)
        reasons[reason] = reasons.get(reason, 0) + 1

    gate = (
        recall >= 0.80
        and filter_fnr <= 0.05
        and precision >= 0.80
        and len(false_positives) == 0
    )
    return GoldenReport(
        dataset_version=dataset["dataset_version"],
        dataset_sha256=hashlib.sha256(raw).hexdigest(),
        generated_at=datetime.now(UTC),
        total_jobs=len(dataset["jobs"]),
        relevant_count=len(relevant_set),
        predicted_count=len(predicted_set),
        precision_at_k=round(precision, 4),
        recall_at_k=round(recall, 4),
        filter_false_negative_rate=round(filter_fnr, 4),
        false_positive_count=len(false_positives),
        top_k_relevance=top_counts,
        miss_reasons=reasons,
        gate_passed=gate,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the golden matching regression")
    parser.add_argument(
        "--dataset",
        default="evaluation/data/golden/golden_v1.json",
    )
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    report = evaluate_golden_dataset(args.dataset)
    if args.report:
        Path(args.report).write_text(
            report.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    print(report.summary())
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
