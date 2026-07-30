"""Chinese labeled benchmark and daily field-trial annotation tools.

M14-001 requires a human-labeled Chinese dataset covering relevance,
duplicates, liveness, links, and hard-filter errors.

M15-001 requires daily Top-10 labels collected during a 7-day field trial.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from jobfindsme.contracts import StrictModel

# ── Label models ────────────────────────────────────────────────────────────


class JobLabel(StrictModel):
    """One human-labeled job from a search result."""

    rank: int = Field(ge=1, le=10)
    job_id: str
    source_name: str
    apply_url: str
    title: str
    company: str
    location: str

    annotated: bool = Field(
        default=False,
        description="True only after a human has reviewed this result.",
    )

    # Core labels
    relevance: int = Field(
        ge=0,
        le=3,
        description="0=不相关 1=弱相关 2=相关 3=完美匹配",
    )
    liveness: Literal["active", "stale", "closed", "unknown"] = Field(
        default="active",
        description="active | stale | closed",
    )
    valid_link: bool = Field(
        default=True,
        description="Whether apply_url loads a real job posting page.",
    )
    duplicate_of: str | None = Field(
        default=None,
        description="job_id of a previously seen same-position posting.",
    )

    # Error flags
    hard_filter_error: bool = Field(
        default=False,
        description="Should have been filtered by hard constraints but wasn't.",
    )
    hard_filter_reason: str = ""

    notes: str = ""


class DailyLabels(StrictModel):
    """One day of labeled Top-10 results."""

    day: int = Field(ge=1, le=7)
    date: str
    plan_id: str
    profile_hash: str
    total_discovered: int
    total_after_filter: int
    duplicates_detected: int = Field(default=0, ge=0)
    source_attempts: tuple[str, ...] = ()
    source_successes: tuple[str, ...] = ()
    labels: tuple[JobLabel, ...]
    source_failures: tuple[str, ...] = ()
    time_to_first_results_seconds: float | None = Field(default=None, ge=0)
    agent_host: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_source_outcomes(self) -> Self:
        unknown_successes = set(self.source_successes) - set(self.source_attempts)
        if unknown_successes:
            raise ValueError("source_successes must be included in source_attempts")
        return self


class DatasetProvenance(StrictModel):
    """Evidence origin used to separate fixtures from observed field data."""

    evidence_kind: Literal["synthetic", "field_trial"] = "synthetic"
    collection_method: Literal[
        "generated_fixture",
        "live_loop_human_annotation",
        "unspecified",
    ] = "unspecified"
    human_annotated: bool = False
    labeler: str | None = None
    date_range: str | None = None
    source_report_paths: tuple[str, ...] = ()
    source_report_sha256: dict[str, str] = Field(default_factory=dict)
    platforms: tuple[str, ...] = ()
    plan: dict[str, Any] = Field(default_factory=dict)
    annotation_guide_version: str | None = None
    notes: str = ""


class LabeledDataset(StrictModel):
    """A versioned, human-labeled Chinese job matching dataset."""

    dataset_version: str
    dataset_type: str = "real_chinese_labeled"
    provenance: DatasetProvenance
    days: tuple[DailyLabels, ...]

    @property
    def all_labels(self) -> tuple[JobLabel, ...]:
        result: list[JobLabel] = []
        for day in self.days:
            result.extend(day.labels)
        return tuple(result)


# ── Daily labeling collector ─────────────────────────────────────────────────


def new_daily_template(
    day: int,
    date: str,
    plan_id: str,
    profile_hash: str,
    jobs: list[dict[str, Any]],
    source_failures: list[str] | None = None,
    source_attempts: list[str] | None = None,
    source_successes: list[str] | None = None,
    duplicates_detected: int = 0,
    total_discovered: int | None = None,
    total_after_filter: int | None = None,
    time_to_first_results_seconds: float | None = None,
    agent_host: str | None = None,
) -> DailyLabels:
    """Create a blank daily labeling template from search results.

    Args:
        day: Trial day number (1-7).
        date: ISO date string.
        plan_id: Search Plan id used for this run.
        profile_hash: SHA256 of the profile facts used.
        jobs: Top-10 job results, each with job_id, source_name, apply_url,
              title, company, location.
        source_failures: Source names that failed during discovery.
    """
    labels = tuple(
        JobLabel(
            rank=index + 1,
            job_id=job["job_id"],
            source_name=job["source_name"],
            apply_url=job.get("apply_url", ""),
            title=job.get("title", ""),
            company=job.get("company", ""),
            location=job.get("location", ""),
            relevance=0,
        )
        for index, job in enumerate(jobs[:10])
    )
    return DailyLabels(
        day=day,
        date=date,
        plan_id=plan_id,
        profile_hash=profile_hash,
        total_discovered=(
            total_discovered if total_discovered is not None else len(jobs)
        ),
        total_after_filter=(
            total_after_filter if total_after_filter is not None else len(jobs)
        ),
        duplicates_detected=duplicates_detected,
        source_attempts=tuple(source_attempts or ()),
        source_successes=tuple(source_successes or ()),
        labels=labels,
        source_failures=tuple(source_failures or ()),
        time_to_first_results_seconds=time_to_first_results_seconds,
        agent_host=agent_host,
    )


def write_daily_template(path: str | Path, template: DailyLabels) -> None:
    """Write a daily labeling template to disk for manual annotation."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            template.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def read_daily_labels(path: str | Path) -> DailyLabels:
    """Read manually filled daily labels from disk."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return DailyLabels.model_validate(data)


def assemble_labeled_dataset(
    version: str,
    provenance: dict[str, Any],
    day_paths: list[str | Path],
) -> LabeledDataset:
    """Combine individual daily label files into a versioned dataset."""
    days = tuple(read_daily_labels(p) for p in day_paths)
    return LabeledDataset(
        dataset_version=version,
        provenance=provenance,
        days=days,
    )


def write_labeled_dataset(path: str | Path, dataset: LabeledDataset) -> None:
    """Write a labeled dataset to disk."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = dataset.model_dump_json(indent=2, exclude_none=True) + "\n"
    target.write_text(raw, encoding="utf-8")


def assemble_field_trial_dataset(
    *,
    version: str,
    labeler: str,
    day_paths: list[str | Path],
    report_paths: list[str | Path],
    annotation_guide_version: str = "0.2",
) -> LabeledDataset:
    """Build claim-verifiable field evidence from labels and immutable Loop reports.

    Inputs are paired by position. This is intentionally strict: a mislabeled day,
    modified report, changed profile, or changed Search Plan must stop assembly
    instead of silently producing plausible-looking metrics.
    """
    from jobfindsme.evaluation.live_loop import LiveSearchLoopReport

    if not labeler.strip():
        raise ValueError("labeler must not be empty")
    if not day_paths:
        raise ValueError("at least one daily label file is required")
    if len(day_paths) != len(report_paths):
        raise ValueError("each daily label file requires exactly one Loop report")

    days = tuple(read_daily_labels(path) for path in day_paths)
    if len({day.day for day in days}) != len(days):
        raise ValueError("daily label files contain duplicate day numbers")
    if any(not label.annotated for day in days for label in day.labels):
        raise ValueError("all labels must be human-reviewed before assembly")
    if len({day.plan_id for day in days}) != 1:
        raise ValueError("all field-trial days must use the same Search Plan")
    if len({day.profile_hash for day in days}) != 1:
        raise ValueError("all field-trial days must use the same confirmed profile")

    pairs = sorted(
        zip(days, report_paths, strict=True),
        key=lambda pair: pair[0].day,
    )
    ordered_days = tuple(day for day, _ in pairs)
    stored_report_paths: list[str] = []
    report_hashes: dict[str, str] = {}
    for day, raw_report_path in pairs:
        report_path = Path(raw_report_path).expanduser().resolve()
        report = LiveSearchLoopReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        if report.plan_id != day.plan_id:
            raise ValueError(f"plan_id mismatch for day {day.day}")
        if report.profile_hash != day.profile_hash:
            raise ValueError(f"profile_hash mismatch for day {day.day}")
        if tuple(job.job_id for job in report.jobs[: len(day.labels)]) != tuple(
            label.job_id for label in day.labels
        ):
            raise ValueError(f"Top job IDs mismatch for day {day.day}")

        stored_path = _portable_path(report_path)
        stored_report_paths.append(stored_path)
        report_hashes[stored_path] = hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()

    date_range = f"{min(day.date for day in days)} to {max(day.date for day in days)}"
    platforms = tuple(
        sorted(
            {
                source
                for day in days
                for source in (
                    *day.source_attempts,
                    *(label.source_name for label in day.labels),
                )
            }
        )
    )
    return LabeledDataset(
        dataset_version=version,
        provenance=DatasetProvenance(
            evidence_kind="field_trial",
            collection_method="live_loop_human_annotation",
            human_annotated=True,
            labeler=labeler.strip(),
            date_range=date_range,
            source_report_paths=tuple(stored_report_paths),
            source_report_sha256=report_hashes,
            platforms=platforms,
            plan={
                "plan_id": ordered_days[0].plan_id,
                "profile_hash": ordered_days[0].profile_hash,
            },
            annotation_guide_version=annotation_guide_version,
            notes="Assembled from immutable Live Loop reports and human labels.",
        ),
        days=ordered_days,
    )


def _portable_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


# ── Metrics helpers shared by runner ─────────────────────────────────────────


def compute_precision_at_k(labels: list[JobLabel], k: int = 10) -> float:
    """Precision@K: fraction of top-K jobs labeled relevant (>=2)."""
    top = labels[:k]
    if not top:
        return 0.0
    return sum(1 for lb in top if lb.relevance >= 2) / len(top)


def compute_ndcg_at_k(labels: list[JobLabel], k: int = 10) -> float:
    """NDCG@K using relevance 0-3 as gain (linear)."""
    import math

    top = labels[:k]
    if not top:
        return 0.0

    def dcg(items: list[JobLabel]) -> float:
        total = 0.0
        for i, lb in enumerate(items):
            gain = lb.relevance  # 0–3
            total += gain / math.log2(i + 2)  # i+2 because i is 0-indexed
        return total

    actual_dcg = dcg(top)
    ideal = sorted(top, key=lambda lb: lb.relevance, reverse=True)
    ideal_dcg = dcg(ideal)
    return actual_dcg / ideal_dcg if ideal_dcg else 0.0


def compute_hard_filter_fnr(labels: list[JobLabel]) -> float:
    """Hard-filter false-negative rate: fraction that should have been filtered."""
    if not labels:
        return 0.0
    return sum(1 for lb in labels if lb.hard_filter_error) / len(labels)


def compute_valid_link_rate(labels: list[JobLabel]) -> float:
    """Fraction of jobs whose apply_url points to a live posting."""
    if not labels:
        return 0.0
    return sum(1 for lb in labels if lb.valid_link) / len(labels)
