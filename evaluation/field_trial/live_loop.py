"""Live search Loop: run, measure, inspect, label, improve.

This module records operational facts without claiming human relevance.  It is
safe to run from an Agent because reports contain only a profile hash and compact
job summaries, never resume text or full job descriptions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import Field

from evaluation.datasets.labels import (
    new_daily_template,
    write_daily_template,
)
from jobfindsme.app import jobfindsmecore
from jobfindsme.contracts import (
    EmploymentType,
    RecruitmentTrack,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SourceRunStatus,
    StrictModel,
)


class LoopJob(StrictModel):
    rank: int = Field(ge=1)
    job_id: str
    source_name: str
    title: str
    company: str
    location: str
    score: float = Field(ge=0, le=1)
    recruitment_track: RecruitmentTrack
    employment_type: EmploymentType
    apply_url: str


class LoopQuality(StrictModel):
    source_success_rate: float = Field(ge=0, le=1)
    url_shape_valid_rate: float = Field(ge=0, le=1)
    required_field_complete_rate: float = Field(ge=0, le=1)
    unknown_track_rate: float = Field(ge=0, le=1)
    unknown_employment_type_rate: float = Field(ge=0, le=1)
    duplicate_apply_urls: int = Field(ge=0)
    average_match_score: float = Field(ge=0, le=1)
    unexpected_result_sources: tuple[str, ...] = ()
    automatic_findings: tuple[str, ...] = ()


class LiveSearchLoopReport(StrictModel):
    schema_version: str = "1.0"
    run_id: str
    agent_host: str
    workspace_id: str
    plan_id: str
    profile_hash: str | None = None
    generated_at: datetime
    diagnostics: SearchRunDiagnostics
    quality: LoopQuality
    jobs: tuple[LoopJob, ...]
    claim_boundary: str = (
        "Automatic checks measure operations and data shape only. "
        "Human labels are required for relevance and real link validity."
    )


def run_live_search_loop(
    core: jobfindsmecore,
    *,
    agent_host: str,
    allow_browser_sources: bool,
    limit: int = 10,
) -> LiveSearchLoopReport:
    """Execute the active Search Plan and return a privacy-minimized report."""

    context = core.context.resolve(require_plan=True)
    if context.plan is None:  # Defensive narrowing for type checkers.
        raise ValueError("no active Search Plan — run setup (with target_roles) first")
    profile = core.profiles.latest_confirmed_summary(
        workspace_id=context.workspace.workspace_id
    )
    result = core.search_jobs_with_diagnostics(
        workspace_id=context.workspace.workspace_id,
        plan_id=context.plan.plan_id,
        allow_browser_sources=allow_browser_sources,
        refresh_mode=SearchRefreshMode.FULL,
        limit=limit,
    )
    from jobfindsme.matching import score_signals

    # The server owns deterministic JobMatch scores. Report the
    # deterministic signal score so averages have operational meaning.
    jobs = tuple(
        LoopJob(
            rank=index,
            job_id=match.job.job_id,
            source_name=match.job.source.source_name,
            title=match.job.title,
            company=match.job.company,
            location=" / ".join(match.job.locations),
            score=score_signals(match.job, profile),
            recruitment_track=match.job.recruitment_track,
            employment_type=match.job.employment_type,
            apply_url=match.job.apply_url,
        )
        for index, match in enumerate(result.matches, start=1)
    )
    return LiveSearchLoopReport(
        run_id=f"loop_{uuid4().hex}",
        agent_host=agent_host,
        workspace_id=context.workspace.workspace_id,
        plan_id=context.plan.plan_id,
        profile_hash=_profile_hash(profile),
        generated_at=datetime.now(UTC),
        diagnostics=result.diagnostics,
        quality=_assess_quality(result.diagnostics, jobs),
        jobs=jobs,
    )


def write_loop_report(path: str | Path, report: LiveSearchLoopReport) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def _profile_hash(profile: object | None) -> str | None:
    if profile is None:
        return None
    payload = profile.model_dump_json(exclude_none=True)  # type: ignore[attr-defined]
    return hashlib.sha256(payload.encode()).hexdigest()


def _assess_quality(
    diagnostics: SearchRunDiagnostics,
    jobs: tuple[LoopJob, ...],
) -> LoopQuality:
    attempted = [
        run
        for run in diagnostics.source_runs
        if run.status is not SourceRunStatus.SKIPPED
    ]
    successful = [run for run in attempted if run.status is SourceRunStatus.SUCCESS]
    urls = [job.apply_url for job in jobs]
    duplicate_urls = len(urls) - len(set(urls))
    findings = []
    failed = [
        run.source_name
        for run in attempted
        if run.status in {SourceRunStatus.FAILED, SourceRunStatus.DEGRADED}
    ]
    if failed:
        findings.append(f"来源失败或降级：{', '.join(failed)}")
    empty_success = [run.source_name for run in successful if run.discovered == 0]
    if empty_success:
        findings.append(f"来源返回 0 条：{', '.join(empty_success)}")
    if duplicate_urls:
        findings.append(f"Top 结果存在 {duplicate_urls} 个重复投递链接")
    attempted_names = {run.source_name for run in diagnostics.source_runs}
    unexpected_sources = tuple(
        sorted({job.source_name for job in jobs} - attempted_names)
    )
    if unexpected_sources:
        findings.append(f"结果混入未参与本轮的来源：{', '.join(unexpected_sources)}")
    if not jobs:
        findings.append("搜索没有返回可评估岗位")
    return LoopQuality(
        source_success_rate=len(successful) / len(attempted) if attempted else 0,
        url_shape_valid_rate=_rate(jobs, lambda job: _valid_http_url(job.apply_url)),
        required_field_complete_rate=_rate(
            jobs,
            lambda job: bool(
                job.title and job.company and job.location and job.apply_url
            ),
        ),
        unknown_track_rate=_rate(
            jobs,
            lambda job: job.recruitment_track is RecruitmentTrack.UNKNOWN,
        ),
        unknown_employment_type_rate=_rate(
            jobs,
            lambda job: job.employment_type is EmploymentType.UNKNOWN,
        ),
        duplicate_apply_urls=duplicate_urls,
        average_match_score=mean(job.score for job in jobs) if jobs else 0,
        unexpected_result_sources=unexpected_sources,
        automatic_findings=tuple(findings),
    )


def _rate(jobs: tuple[LoopJob, ...], predicate) -> float:
    # Vacuous truth: no jobs → no violations, rate is 1.0.  Reporting 0.0
    # here used to mislead "no results" into "all results invalid".
    return sum(1 for job in jobs if predicate(job)) / len(jobs) if jobs else 1.0


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one measured live-search Loop.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("~/.jobfindsme/data/jobfindsme.db").expanduser(),
    )
    parser.add_argument("--agent-host", default="manual")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--allow-browser-sources", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--day", type=int)
    parser.add_argument("--annotation-output", type=Path)
    args = parser.parse_args()

    report = run_live_search_loop(
        jobfindsmecore(args.db),
        agent_host=args.agent_host,
        allow_browser_sources=args.allow_browser_sources,
        limit=args.limit,
    )
    output = args.output or (
        Path("~/.jobfindsme/reports").expanduser()
        / f"{report.generated_at:%Y%m%dT%H%M%SZ}-{report.run_id}.json"
    )
    write_loop_report(output, report)
    if args.day is not None:
        annotation_output = args.annotation_output or output.with_name(
            f"{output.stem}-labels.json"
        )
        template = new_daily_template(
            day=args.day,
            date=report.generated_at.date().isoformat(),
            plan_id=report.plan_id,
            profile_hash=report.profile_hash or "no-profile",
            jobs=[job.model_dump(mode="json") for job in report.jobs],
            source_attempts=[
                run.source_name
                for run in report.diagnostics.source_runs
                if run.status is not SourceRunStatus.SKIPPED
            ],
            source_successes=[
                run.source_name
                for run in report.diagnostics.source_runs
                if run.status is SourceRunStatus.SUCCESS
            ],
            source_failures=[
                run.source_name
                for run in report.diagnostics.source_runs
                if run.status in {SourceRunStatus.FAILED, SourceRunStatus.DEGRADED}
            ],
            duplicates_detected=report.diagnostics.duplicates_removed,
            total_discovered=report.diagnostics.total_discovered,
            total_after_filter=report.diagnostics.result_count,
            time_to_first_results_seconds=report.diagnostics.elapsed_seconds,
            agent_host=report.agent_host,
        )
        write_daily_template(annotation_output, template)
    print(json.dumps({"report": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
