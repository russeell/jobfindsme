"""Create a human-labeling template from jobfindsme JSON search output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jobfindsme.evaluation.labeling import new_daily_template, write_daily_template


def _job_view(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize either a JobMatch or compact JobMatchSummary JSON object."""
    job = item.get("job", item)
    source = job.get("source", {})
    locations = job.get("locations", ())
    return {
        "job_id": job["job_id"],
        "source_name": job.get("source_name") or source.get("source_name", "unknown"),
        "apply_url": job.get("apply_url", ""),
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": " / ".join(locations),
    }


def read_search_results(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSON list or a mapping containing a ``jobs``/``results`` list."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("jobs", payload.get("results"))
    else:
        items = None
    if not isinstance(items, list):
        raise ValueError("search result JSON must be a list or contain jobs/results")
    return [_job_view(item) for item in items]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create an unannotated M14/M15 daily Top-10 template."
    )
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--profile-hash", required=True)
    parser.add_argument("--source-attempt", action="append", default=[])
    parser.add_argument("--source-success", action="append", default=[])
    parser.add_argument("--source-failure", action="append", default=[])
    parser.add_argument("--duplicates-detected", type=int, default=0)
    parser.add_argument("--total-discovered", type=int)
    parser.add_argument("--total-after-filter", type=int)
    parser.add_argument("--time-to-first-results-seconds", type=float)
    parser.add_argument("--agent-host")
    args = parser.parse_args()

    jobs = read_search_results(args.jobs)
    template = new_daily_template(
        day=args.day,
        date=args.date,
        plan_id=args.plan_id,
        profile_hash=args.profile_hash,
        jobs=jobs,
        source_attempts=args.source_attempt,
        source_successes=args.source_success,
        source_failures=args.source_failure,
        duplicates_detected=args.duplicates_detected,
        total_discovered=args.total_discovered,
        total_after_filter=args.total_after_filter,
        time_to_first_results_seconds=args.time_to_first_results_seconds,
        agent_host=args.agent_host,
    )
    write_daily_template(args.output, template)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
