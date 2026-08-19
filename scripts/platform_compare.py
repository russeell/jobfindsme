"""Layer-3 helper: real-platform comparison vs manual sampling.

Run a real search, dump the result to CSV, then manually sample the same
query on BOSS直聘 / 猎聘 (top 30-50) and mark:

    平台有，jobfindsme 没抓到        -> coverage gap
    抓到了，但被 filter 错杀         -> filter gap
    留下来了，但 rank 太低           -> ranking gap

Usage:
    python scripts/platform_compare.py --role "AI应用工程师" --city 深圳 \
        --salary-min-k 20 --output /tmp/platform_compare.csv
"""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path

from jobfindsme.app import jobfindsmecore


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-platform comparison helper")
    parser.add_argument("--role", default="AI应用工程师")
    parser.add_argument("--city", action="append", default=["上海"])
    parser.add_argument("--salary-min-k", type=int, default=20)
    parser.add_argument("--track", default="social")
    parser.add_argument("--type", default="full_time")
    parser.add_argument("--output", default="/tmp/platform_compare.csv")
    args = parser.parse_args()

    core = jobfindsmecore(Path(tempfile.mkdtemp()) / "compare.db")
    core.configure_search(
        target_role=args.role,
        locations=args.city,
        salary_min_k=args.salary_min_k,
        recruitment_track=args.track,
        employment_type=args.type,
    )
    result = core.search_jobs_with_diagnostics(
        refresh_mode="live",
        include_seen=True,
    )

    rows = []
    for rank, match in enumerate(result.matches, start=1):
        job = match.job
        rows.append(
            {
                "rank": rank,
                "title": job.title,
                "company": job.company,
                "city": "、".join(job.locations),
                "salary": job.salary.raw_text if job.salary else "",
                "score": match.score,
                "change": match.change_type.value,
                "source": job.source.source_name,
                "apply_url": job.apply_url,
            }
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["rank"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"matched {len(rows)} jobs -> {output}")
    for run in result.diagnostics.source_runs:
        print(f"  {run.source_name}: {run.status.value} ({run.discovered})")
    print(
        "manual step: sample the same query on BOSS/猎聘 (top 30-50) and "
        "mark coverage / filter / ranking gaps against this CSV."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
