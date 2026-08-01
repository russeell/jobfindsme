"""L1–L4 evaluation tools: snapshot replay, pairwise compare, time diff.

L1 – Save/load job snapshots and replay through the current matcher.
L3 – Pairwise comparison of baseline vs candidate match results.
L4 – Time-window differ between two Live Loop reports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jobfindsme.contracts import JobMatch, JobPosting, SearchPlan, StrictModel
from jobfindsme.evaluation.regression.legacy_matcher import LegacyBM25Matcher

# ── L1: Snapshot save / replay ───────────────────────────────────────────────


def save_job_snapshot(
    jobs: list[JobPosting],
    path: str | Path,
    *,
    plan: SearchPlan | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Persist a list of JobPosting objects as a versioned fixture.

    Returns the written path for provenance tracking.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "jobfindsme-snapshot-v1",
        "saved_at": datetime.now().isoformat(),
        "count": len(jobs),
        "plan": plan.model_dump(mode="json") if plan else None,
        "metadata": metadata or {},
        "jobs": [job.model_dump(mode="json") for job in jobs],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_job_snapshot(path: str | Path) -> Snapshot:
    """Load a saved job snapshot fixture."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    jobs = [JobPosting.model_validate(j) for j in data["jobs"]]
    plan = SearchPlan.model_validate(data["plan"]) if data.get("plan") else None
    return Snapshot(
        path=str(path),
        saved_at=data["saved_at"],
        plan=plan,
        metadata=data.get("metadata", {}),
        jobs=jobs,
    )


@dataclass(frozen=True)
class Snapshot:
    path: str
    saved_at: str
    plan: SearchPlan | None
    metadata: dict[str, Any]
    jobs: list[JobPosting]


# ── L1: Replay ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReplayResult:
    snapshot_path: str
    replayed_at: str
    total_jobs: int
    passed_filter: int
    matches: list[JobMatch]

    @property
    def score_summary(self) -> dict[str, float]:
        if not self.matches:
            return {"min": 0, "max": 0, "mean": 0, "median": 0}
        scores = sorted(m.score for m in self.matches)
        n = len(scores)
        return {
            "min": scores[0],
            "max": scores[-1],
            "mean": sum(scores) / n,
            "median": scores[n // 2],
        }


def replay_snapshot(
    snapshot: Snapshot,
    plan: SearchPlan,
    *,
    limit: int = 20,
    min_score: float = 0.10,
) -> ReplayResult:
    """Run the current matcher against saved job fixtures.

    Use this to detect regressions: save a snapshot before a code change,
    replay it afterward, and compare the results.
    """
    matcher = LegacyBM25Matcher()
    matches = matcher.match(
        plan,
        snapshot.jobs,
        limit=limit,
        min_score=min_score,
    )
    return ReplayResult(
        snapshot_path=snapshot.path,
        replayed_at=datetime.now().isoformat(),
        total_jobs=len(snapshot.jobs),
        passed_filter=len(matches),
        matches=matches,
    )


# ── L3: Pairwise comparator ──────────────────────────────────────────────────


class DiffItem(StrictModel):
    job_id: str
    title: str = ""
    source_name: str = ""
    baseline_rank: int | None = None
    candidate_rank: int | None = None
    baseline_score: float | None = None
    candidate_score: float | None = None
    score_delta: float = 0.0
    change: str = ""  # new / removed / up / down / unchanged


class PairwiseReport(StrictModel):
    baseline_label: str
    candidate_label: str
    generated_at: str
    total_baseline: int
    total_candidate: int
    new_jobs: int
    removed_jobs: int
    score_improved: int
    score_declined: int
    unchanged: int
    diffs: tuple[DiffItem, ...]

    def summary(self) -> str:
        return (
            f"Baseline ({self.baseline_label}) → "
            f"Candidate ({self.candidate_label})\n"
            f"  Baseline:  {self.total_baseline} results\n"
            f"  Candidate: {self.total_candidate} results\n"
            f"  New:       {self.new_jobs}\n"
            f"  Removed:   {self.removed_jobs}\n"
            f"  Improved:  {self.score_improved}\n"
            f"  Declined:  {self.score_declined}\n"
            f"  Unchanged: {self.unchanged}"
        )


def compare_results(
    baseline: list[JobMatch],
    candidate: list[JobMatch],
    *,
    baseline_label: str = "baseline",
    candidate_label: str = "candidate",
) -> PairwiseReport:
    """Compare two match result sets and report per-job diffs."""
    base_map = {m.job.job_id: m for m in baseline}
    cand_map = {m.job.job_id: m for m in candidate}
    all_ids = set(base_map) | set(cand_map)

    diffs: list[DiffItem] = []
    new_jobs = removed_jobs = improved = declined = unchanged = 0

    for job_id in sorted(all_ids):
        b = base_map.get(job_id)
        c = cand_map.get(job_id)
        if b and not c:
            removed_jobs += 1
            diffs.append(
                DiffItem(
                    job_id=job_id,
                    title=b.job.title,
                    source_name=b.job.source.source_name,
                    baseline_rank=_rank_of(baseline, job_id),
                    baseline_score=b.score,
                    change="removed",
                )
            )
        elif c and not b:
            new_jobs += 1
            diffs.append(
                DiffItem(
                    job_id=job_id,
                    title=c.job.title,
                    source_name=c.job.source.source_name,
                    candidate_rank=_rank_of(candidate, job_id),
                    candidate_score=c.score,
                    change="new",
                )
            )
        else:
            assert b and c
            delta = c.score - b.score
            if abs(delta) < 0.0001:
                unchanged += 1
                change = "unchanged"
            elif delta > 0:
                improved += 1
                change = "up"
            else:
                declined += 1
                change = "down"
            diffs.append(
                DiffItem(
                    job_id=job_id,
                    title=b.job.title,
                    source_name=b.job.source.source_name,
                    baseline_rank=_rank_of(baseline, job_id),
                    candidate_rank=_rank_of(candidate, job_id),
                    baseline_score=b.score,
                    candidate_score=c.score,
                    score_delta=round(delta, 6),
                    change=change,
                )
            )

    diffs.sort(key=lambda d: abs(d.score_delta), reverse=True)
    return PairwiseReport(
        baseline_label=baseline_label,
        candidate_label=candidate_label,
        generated_at=datetime.now().isoformat(),
        total_baseline=len(baseline),
        total_candidate=len(candidate),
        new_jobs=new_jobs,
        removed_jobs=removed_jobs,
        score_improved=improved,
        score_declined=declined,
        unchanged=unchanged,
        diffs=tuple(diffs),
    )


def _rank_of(matches: list[JobMatch], job_id: str) -> int | None:
    for i, m in enumerate(matches, 1):
        if m.job.job_id == job_id:
            return i
    return None


# ── L4: Time-window differ ───────────────────────────────────────────────────


class WindowDiffItem(StrictModel):
    job_id: str
    title: str = ""
    source_name: str = ""
    change: str = ""  # new / changed / reopened / closed / unchanged


class WindowDiffReport(StrictModel):
    earlier_label: str
    later_label: str
    generated_at: str
    earlier_total: int
    later_total: int
    new_jobs: int
    changed_jobs: int
    reopened_jobs: int
    closed_jobs: int
    unchanged_jobs: int
    items: tuple[WindowDiffItem, ...]

    def summary(self) -> str:
        return (
            f"Window diff: {self.earlier_label} → {self.later_label}\n"
            f"  Earlier:  {self.earlier_total} jobs\n"
            f"  Later:    {self.later_total} jobs\n"
            f"  New:      {self.new_jobs}\n"
            f"  Changed:  {self.changed_jobs}\n"
            f"  Reopened: {self.reopened_jobs}\n"
            f"  Closed:   {self.closed_jobs}\n"
            f"  Unchanged:{self.unchanged_jobs}"
        )


def diff_loop_reports(
    earlier_path: str | Path,
    later_path: str | Path,
    *,
    earlier_label: str = "earlier",
    later_label: str = "later",
) -> WindowDiffReport:
    """Diff two Live Loop reports to identify new, changed, and closed jobs."""
    from jobfindsme.evaluation.field_trial.live_loop import LiveSearchLoopReport

    earlier = LiveSearchLoopReport.model_validate_json(
        Path(earlier_path).read_text(encoding="utf-8")
    )
    later = LiveSearchLoopReport.model_validate_json(
        Path(later_path).read_text(encoding="utf-8")
    )

    old_map = {job.job_id: job for job in earlier.jobs}
    new_map = {job.job_id: job for job in later.jobs}
    # Also check by title+source for jobs that got new IDs
    old_by_key = {(job.title.casefold(), job.source_name): job for job in earlier.jobs}

    all_ids = set(old_map) | set(new_map)
    items: list[WindowDiffItem] = []
    new_count = changed_count = reopened_count = closed_count = unchanged_count = 0

    for job_id in sorted(all_ids):
        old_job = old_map.get(job_id)
        new_job = new_map.get(job_id)

        if old_job and not new_job:
            # Check if same job appeared under different ID (still present)
            key = (old_job.title.casefold(), old_job.source_name)
            if (
                key in old_by_key
                and old_by_key[key].job_id != job_id
                and old_by_key[key].job_id in new_map
            ):
                continue  # job still exists under a different ID
            closed_count += 1
            items.append(
                WindowDiffItem(
                    job_id=job_id,
                    title=old_job.title,
                    source_name=old_job.source_name,
                    change="closed",
                )
            )
        elif new_job and not old_job:
            # Check if it's a reopened job (same title+source was closed)
            key = (new_job.title.casefold(), new_job.source_name)
            if key in old_by_key and old_by_key[key].job_id != job_id:
                reopened_count += 1
                items.append(
                    WindowDiffItem(
                        job_id=job_id,
                        title=new_job.title,
                        source_name=new_job.source_name,
                        change="reopened",
                    )
                )
            else:
                new_count += 1
                items.append(
                    WindowDiffItem(
                        job_id=job_id,
                        title=new_job.title,
                        source_name=new_job.source_name,
                        change="new",
                    )
                )
        elif old_job and new_job:
            if abs(new_job.score - old_job.score) > 0.001:
                changed_count += 1
                items.append(
                    WindowDiffItem(
                        job_id=job_id,
                        title=new_job.title,
                        source_name=new_job.source_name,
                        change="changed",
                    )
                )
            else:
                unchanged_count += 1

    return WindowDiffReport(
        earlier_label=earlier_label,
        later_label=later_label,
        generated_at=datetime.now().isoformat(),
        earlier_total=len(earlier.jobs),
        later_total=len(later.jobs),
        new_jobs=new_count,
        changed_jobs=changed_count,
        reopened_jobs=reopened_count,
        closed_jobs=closed_count,
        unchanged_jobs=unchanged_count,
        items=tuple(items),
    )


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="L1–L4 evaluation tools: snapshot replay, compare, diff"
    )
    sub = parser.add_subparsers(dest="command")

    # replay
    replay_p = sub.add_parser("replay", help="Replay snapshot through matcher")
    replay_p.add_argument("--snapshot", required=True)
    replay_p.add_argument("--plan", required=True, help="Path to plan JSON")

    # compare
    cmp_p = sub.add_parser("compare", help="Compare two match result JSON files")
    cmp_p.add_argument("--baseline", required=True)
    cmp_p.add_argument("--candidate", required=True)
    cmp_p.add_argument("--baseline-label", default="baseline")
    cmp_p.add_argument("--candidate-label", default="candidate")
    cmp_p.add_argument("--output", default=None)

    # diff
    diff_p = sub.add_parser("diff", help="Diff two Live Loop reports")
    diff_p.add_argument("--earlier", required=True)
    diff_p.add_argument("--later", required=True)
    diff_p.add_argument("--earlier-label", default="earlier")
    diff_p.add_argument("--later-label", default="later")
    diff_p.add_argument("--output", default=None)

    args = parser.parse_args()

    if args.command == "replay":
        snapshot = load_job_snapshot(args.snapshot)
        plan_data = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        plan = SearchPlan.model_validate(plan_data)
        result = replay_snapshot(snapshot, plan)
        print(
            f"Replayed {result.total_jobs} jobs: {result.passed_filter} passed filter"
        )
        print(f"Scores: {result.score_summary}")
        for m in result.matches[:5]:
            print(f"  {m.score:.4f} | {m.job.title[:40]} | {m.job.source.source_name}")
        return 0

    if args.command == "compare":
        baseline_data = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        candidate_data = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        baseline = _matches_from_json(baseline_data)
        candidate = _matches_from_json(candidate_data)
        report = compare_results(
            baseline,
            candidate,
            baseline_label=args.baseline_label,
            candidate_label=args.candidate_label,
        )
        print(report.summary())
        if args.output:
            Path(args.output).write_text(
                report.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        return 0

    if args.command == "diff":
        report = diff_loop_reports(
            args.earlier,
            args.later,
            earlier_label=args.earlier_label,
            later_label=args.later_label,
        )
        print(report.summary())
        if args.output:
            Path(args.output).write_text(
                report.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        return 0

    parser.print_help()
    return 1


def _matches_from_json(data: dict | list) -> list[JobMatch]:
    """Parse match results from a JSON dict or list."""
    if isinstance(data, list):
        items = data
    else:
        items = data.get("jobs", data.get("matches", []))
    if not items:
        return []
    result: list[JobMatch] = []
    for item in items:
        if "job" in item and "score" in item:
            job = JobPosting.model_validate(item["job"])
            result.append(
                JobMatch(
                    job=job,
                    score=item.get("score", 0),
                    evidence=item.get("evidence"),
                )
            )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
