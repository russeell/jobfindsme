"""Multi-day Radar replay: compress a week of usage into deterministic days.

Each day is a JSON job-snapshot file (same format as `jobfindsme jobs import`).
The harness imports the day, refreshes the json_file source (so missing jobs
are marked closed), runs an incremental radar search, and records the change
outcome.  A fixture set lives in ``evaluation/data/radar_replay/``.

Expected transitions for the shipped fixtures:

    Day 1: A, B, C        -> all NEW
    Day 2: + D            -> D NEW; A/B/C suppressed
    Day 3: A salary change,
           B missing,
           C + C-dup,
           D changed (but applied),
           + E             -> A CHANGED, B CLOSED, C/C-dup suppressed,
                              D suppressed (applied), E NEW
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobfindsme.app import jobfindsmecore
from jobfindsme.contracts import DiscoverySource, JobStateKind, StrictModel
from jobfindsme.importing.discovery import refresh_sources
from jobfindsme.importing.parsers import parse_json


class DayOutcome(StrictModel):
    day: int
    shown_ids: tuple[str, ...]
    change_types: dict[str, str]
    new: int = 0
    changed: int = 0
    reopened: int = 0
    closed: int = 0
    repeated_suppressed: int = 0


class RadarReplayReport(StrictModel):
    generated_at: datetime
    days: tuple[DayOutcome, ...]
    applied_job_ids: tuple[str, ...] = ()

    def summary(self) -> str:
        lines = [f"Radar replay: {len(self.days)} days"]
        for outcome in self.days:
            lines.append(
                f"  Day {outcome.day}: shown={list(outcome.shown_ids)} "
                f"new={outcome.new} changed={outcome.changed} "
                f"closed={outcome.closed} suppressed={outcome.repeated_suppressed}"
            )
        if self.applied_job_ids:
            lines.append(
                f"  Applied (never re-suggested): {list(self.applied_job_ids)}"
            )
        return "\n".join(lines)


def run_radar_replay(
    day_paths: Sequence[str | Path],
    *,
    database_path: str | Path | None = None,
    role: str = "AI应用工程师",
    source_name: str = "回放岗位",
    apply_after_days: Sequence[tuple[int, str]] = (),
    tmp_dir: str | Path | None = None,
) -> tuple[RadarReplayReport, Any]:
    """Replay day snapshots through the real radar pipeline.

    Returns (report, core) so tests can inspect state (e.g. applied jobs).
    """
    import tempfile

    paths = [Path(path) for path in day_paths]
    if database_path is None:
        database_path = Path(tempfile.mkdtemp(dir=tmp_dir)) / "radar_replay.db"
    core = jobfindsmecore(database_path)
    placeholder = DiscoverySource(
        kind="json_file",
        source_name=source_name,
        path=str(paths[0]),
    )
    core.configure_search(target_role=role, sources=(placeholder,))
    workspace_id = core.context.resolve_workspace().workspace_id

    outcomes: list[DayOutcome] = []
    applied: list[str] = []
    for index, path in enumerate(paths, start=1):
        source = DiscoverySource(
            kind="json_file",
            source_name=source_name,
            path=str(path),
        )
        records = parse_json(path.read_text(encoding="utf-8"), source_name=source_name)
        core.job_imports.import_records(workspace_id, records)
        refresh_sources(
            workspace_id=workspace_id,
            plan_id=None,
            sources=(source,),
            allow_browser=False,
            discovery=core.discovery,
            jobs=core.jobs,
            subscriptions=core.source_subscriptions,
        )
        result = core.search_jobs_with_diagnostics(
            refresh_mode="cache",
            include_seen=False,
        )
        shown = {match.job.job_id: match for match in result.matches}
        outcomes.append(
            DayOutcome(
                day=index,
                shown_ids=tuple(shown),
                change_types={
                    job_id: match.change_type.value for job_id, match in shown.items()
                },
                new=result.changes.new,
                changed=result.changes.changed,
                reopened=result.changes.reopened,
                closed=result.changes.closed,
                repeated_suppressed=result.changes.repeated_suppressed,
            )
        )
        for day, job_id in apply_after_days:
            if day == index:
                stored = next(
                    (
                        job.job_id
                        for job in core.jobs.list(workspace_id)
                        if job.external_id == job_id
                    ),
                    None,
                )
                if stored is None:
                    raise LookupError(f"job {job_id!r} not found in day {index}")
                core.update_job_state(
                    job_id=stored,
                    state=JobStateKind.APPLIED,
                )
                applied.append(stored)

    report = RadarReplayReport(
        generated_at=datetime.now(UTC),
        days=tuple(outcomes),
        applied_job_ids=tuple(applied),
    )
    return report, core


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Replay multi-day radar fixtures")
    parser.add_argument(
        "--days",
        nargs="+",
        default=[
            "evaluation/data/radar_replay/day1.json",
            "evaluation/data/radar_replay/day2.json",
            "evaluation/data/radar_replay/day3.json",
        ],
    )
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report, _ = run_radar_replay(args.days)
    if args.output:
        Path(args.output).write_text(
            report.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DayOutcome", "RadarReplayReport", "run_radar_replay"]
