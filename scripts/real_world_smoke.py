from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobfindsme.app import jobfindsmecore
from jobfindsme.cli import default_database_path
from jobfindsme.contracts import (
    EmploymentType,
    RecruitmentTrack,
    SearchRefreshMode,
    SourceRunStatus,
)
from jobfindsme.doctor import Doctor
from jobfindsme.mcp import ToolRegistry
from jobfindsme.presentation import format_search_results

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "evaluation" / "evidence"


def _source_family(source_name: str) -> str:
    if "BOSS" in source_name:
        return "BOSS直聘"
    if "猎聘" in source_name:
        return "猎聘"
    if "智联" in source_name:
        return "智联招聘"
    if "前程" in source_name or "51job" in source_name:
        return "前程无忧"
    return source_name.split("·", 1)[0]


def _top_counts(matches: tuple[Any, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        family = _source_family(match.job.source.source_name)
        counts[family] = counts.get(family, 0) + 1
    return counts


def _source_rows(
    source_runs: tuple[Any, ...],
) -> list[dict]:
    rows = []
    for run in source_runs:
        family = _source_family(run.source_name)
        rows.append(
            {
                "source": run.source_name,
                "family": family,
                "kind": run.source_kind.value,
                "status": run.status.value,
                "elapsed_seconds": round(run.elapsed_seconds, 3),
                "discovered": run.discovered,
                "unique": run.unique,
                "versions_created": run.versions_created,
                "cache_used": run.cache_used,
                "top_count": run.top_results,
                "error": run.error,
            }
        )
    return rows


def _doctor_dict(report: Any) -> dict:
    return report.model_dump(mode="json")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _public_database_path(path: Path) -> str:
    expanded = path.expanduser()
    default = default_database_path().expanduser()
    if expanded == default:
        return str(default).replace(str(Path.home()), "~")
    return "<custom local database>"


def _public_value(value: Any) -> Any:
    home = str(Path.home())
    if isinstance(value, str):
        return value.replace(home, "~")
    if isinstance(value, dict):
        return {key: _public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    return value


def _status_mark(status: str) -> str:
    return {
        SourceRunStatus.SUCCESS.value: "SUCCESS",
        SourceRunStatus.DEGRADED.value: "DEGRADED",
        SourceRunStatus.FAILED.value: "FAILED",
        SourceRunStatus.SKIPPED.value: "SKIPPED",
    }.get(status, status.upper())


def _markdown_report(payload: dict) -> str:
    lines = [
        "# Agent Job Search Real-World Source Report",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Database: `{payload['database']}`",
        f"- Query: role={payload['query']['target_role']}, "
        f"locations={payload['query']['locations']}, "
        f"salary_min_k={payload['query']['salary_min_k']}",
        f"- End-to-end elapsed: `{payload['search']['elapsed_seconds']}s`",
        f"- Remote discovered: `{payload['search']['total_discovered']}`",
        f"- Unique imported: `{payload['search']['total_unique']}`",
        f"- Top results: `{payload['search']['result_count']}`",
        "",
        "## Sources",
        "",
        "| Source | Status | Time | Found | Unique | Top | Cache | Error |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["sources"]:
        error = (row.get("error") or "").replace("\n", " ")[:120]
        lines.append(
            f"| {row['source']} | {_status_mark(row['status'])} | "
            f"{row['elapsed_seconds']}s | {row['discovered']} | "
            f"{row['unique']} | {row['top_count']} | "
            f"{'yes' if row['cache_used'] else 'no'} | {error} |"
        )
    lines.extend(
        [
            "",
            "## MCP Smoke",
            "",
            f"- Doctor OK: `{payload['smoke']['doctor_ok']}`",
            f"- Configure OK: `{payload['smoke']['configure_ok']}`",
            f"- Search OK: `{payload['smoke']['search_ok']}`",
            f"- Factual layers present: `{payload['smoke']['layers_present']}`",
            f"- Link present: `{payload['smoke']['link_present']}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=default_database_path())
    parser.add_argument("--role", default="AI应用工程师")
    parser.add_argument("--city", action="append")
    parser.add_argument("--salary-min-k", type=int, default=20)
    parser.add_argument("--experience-max-years", type=int, default=3)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--refresh-mode",
        choices=("live", "cache"),
        default="live",
    )
    parser.add_argument(
        "--allow-browser-sources",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--include-seen",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--allow-cache-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--use-profile",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--reports-dir", type=Path, default=REPORT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    cities = tuple(args.city or ("上海", "深圳"))
    core = jobfindsmecore(args.db)
    registry = ToolRegistry(core)

    doctor = Doctor(args.db).run()
    config_response = registry.call(
        "setup",
        {
            "target_role": args.role,
            "locations": cities,
            "salary_min_k": args.salary_min_k,
            "experience_max_years": args.experience_max_years,
            "recruitment_track": RecruitmentTrack.SOCIAL.value,
            "employment_type": EmploymentType.FULL_TIME.value,
        },
    )
    configure_ok = config_response.get("isError") is False
    if not configure_ok:
        message = config_response.get("content", [{}])[0].get(
            "text", "setup failed without an error message"
        )
        raise RuntimeError(f"real-world smoke setup failed: {message}")
    result = core.search_jobs_with_diagnostics(
        limit=args.limit,
        allow_browser_sources=args.allow_browser_sources,
        refresh_mode=SearchRefreshMode(args.refresh_mode),
        allow_cache_fallback=args.allow_cache_fallback,
        include_seen=args.include_seen,
        use_profile=args.use_profile,
    )
    presentation = core.search_presentation_context(use_profile=args.use_profile)
    jobs = [
        {
            "job": core.list_job_summaries(
                job_ids=[match.job.job_id],
                limit=1,
            )[0],
            "score": match.score,
            "evidence": match.evidence,
            "state": match.state,
            "first_seen_at": match.first_seen_at,
            "change_type": match.change_type,
        }
        for match in result.matches
    ]
    final_text = format_search_results(
        jobs,
        result.changes,
        result.diagnostics,
        presentation,
    )
    mcp_search = registry.call(
        "search_jobs",
        {
            "refresh_mode": "cache",
            "include_seen": True,
            "allow_browser_sources": False,
            "limit": min(args.limit, 20),
            "use_profile": args.use_profile,
        },
    )
    mcp_text = (
        mcp_search.get("content", [{}])[0].get("text", "")
        if mcp_search.get("isError") is False
        else ""
    )
    top_counts = _top_counts(result.matches)
    payload = {
        "generated_at": generated_at,
        "database": _public_database_path(args.db),
        "query": {
            "target_role": args.role,
            "locations": cities,
            "salary_min_k": args.salary_min_k,
            "experience_max_years": args.experience_max_years,
            "recruitment_track": "social",
            "employment_type": "full_time",
        },
        "doctor": _public_value(_doctor_dict(doctor)),
        "search": {
            "elapsed_seconds": round(result.diagnostics.elapsed_seconds, 3),
            "matching_seconds": round(result.diagnostics.matching_seconds, 3),
            "total_discovered": result.diagnostics.total_discovered,
            "total_unique": result.diagnostics.total_unique,
            "duplicates_removed": result.diagnostics.duplicates_removed,
            "result_count": result.diagnostics.result_count,
            "new_count": result.diagnostics.new_count,
            "changed_count": result.diagnostics.changed_count,
            "reopened_count": result.diagnostics.reopened_count,
            "closed_count": result.diagnostics.closed_count,
        },
        "sources": _source_rows(result.diagnostics.source_runs),
        "top_counts": top_counts,
        "smoke": {
            "doctor_ok": doctor.ok,
            "configure_ok": configure_ok,
            "search_ok": mcp_search.get("isError") is False,
            "layers_present": all(
                heading in mcp_text
                for heading in ("【搜索摘要】", "【推荐岗位】", "【状态与下一步】")
            ),
            "link_present": "投递链接：http" in mcp_text,
        },
        "final_text": final_text,
    }
    stamp = generated_at.replace(":", "").replace("-", "")[:15]
    json_path = args.reports_dir / f"four_source_search_{stamp}.json"
    md_path = args.reports_dir / f"four_source_search_{stamp}.md"
    latest_json = args.reports_dir / "latest_four_source_search.json"
    latest_md = args.reports_dir / "latest_four_source_search.md"
    _write_json(json_path, payload)
    _write_json(latest_json, payload)
    markdown = _markdown_report(payload)
    md_path.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "ok": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
