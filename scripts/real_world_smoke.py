from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobfindsme.cli import default_database_path
from jobfindsme.contracts import (
    EmploymentType,
    RecruitmentTrack,
    SearchRefreshMode,
    SourceRunStatus,
)
from jobfindsme.core import jobfindsmecore
from jobfindsme.doctor import Doctor
from jobfindsme.mcp import ToolRegistry
from jobfindsme.presentation import format_search_results

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "real-world"


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
    top_counts: dict[str, int],
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
                "top_count": top_counts.get(family, 0),
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
        return "~/.jobfindsme/data/jobfindsme.db"
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
        "# jobfindsme Real-World Source Report",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Database: `{payload['database']}`",
        f"- Query: roles={payload['query']['target_roles']}, "
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
            f"- Sections present: `{payload['smoke']['sections_present']}`",
            f"- Link present: `{payload['smoke']['link_present']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_terminal_text(final_text: str, *, max_jobs: int = 4) -> str:
    """Keep a README screenshot short while preserving the real contract."""
    lines = []
    current_job = 0
    in_jobs = False
    skipped = 0
    for line in final_text.splitlines():
        if line.startswith("【4·岗位列表】"):
            in_jobs = True
            lines.append(line)
            continue
        if line.startswith("【5·说明】"):
            in_jobs = False
            if skipped:
                lines.extend(
                    [
                        "",
                        f"... 其余 {skipped} 个岗位已省略，实际输出包含完整链接。",
                    ]
                )
            lines.append(line)
            continue
        if in_jobs:
            if re.match(r"^\d+\.\s", line):
                current_job += 1
            if current_job > max_jobs:
                if line.strip():
                    skipped += 1 if re.match(r"^\d+\.\s", line) else 0
                continue
        lines.append(line)
    return _display_safe_text("\n".join(lines))


def _display_safe_text(text: str) -> str:
    """Avoid glyphs that common GitHub/OS screenshot fonts render poorly."""
    return (
        text.replace("✓", "OK")
        .replace("△", "CACHE")
        .replace("✗", "FAILED")
        .replace("📬", "定时")
        .replace("📋", "历史")
    )


def _write_terminal_asset(path: Path, prompt: str, final_text: str) -> None:
    """Render a terminal-style PNG without exposing local paths or IDs."""
    from PIL import Image, ImageDraw

    width = 1280
    padding_x = 44
    max_text_width = width - padding_x * 2
    font = _load_font(20)
    font_bold = _load_font(22)
    title_font = _load_font(16)
    compact = _compact_terminal_text(final_text)
    raw_lines = [f"$ {prompt}", ""] + compact.splitlines()
    wrapped: list[tuple[str, str]] = []
    for line in raw_lines:
        style = "prompt" if line.startswith("$ ") else "line"
        wrapped.extend((style, item) for item in _wrap_line(line, font, max_text_width))
    line_height = 30
    header_height = 58
    height = min(2000, header_height + 34 + line_height * len(wrapped))
    image = Image.new("RGB", (width, height), "#0b0f14")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, header_height), fill="#111827")
    draw.ellipse((24, 21, 40, 37), fill="#ff5f57")
    draw.ellipse((50, 21, 66, 37), fill="#febc2e")
    draw.ellipse((76, 21, 92, 37), fill="#28c840")
    draw.text(
        (112, 20),
        "jobfindsme real MCP output",
        fill="#94a3b8",
        font=title_font,
    )
    y = header_height + 28
    for style, line in wrapped:
        if y > height - 36:
            draw.text(
                (padding_x, y),
                "... 输出已截断，真实结果保留完整岗位和链接",
                fill="#94a3b8",
                font=font,
            )
            break
        fill = "#f9fafb" if style == "prompt" else "#d1d5db"
        active_font = font_bold if style == "prompt" else font
        draw.text((padding_x, y), line, fill=fill, font=active_font)
        y += line_height
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _load_font(size: int):
    from PIL import ImageFont

    candidates = (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrap_line(line: str, font: Any, max_width: int) -> list[str]:
    if not line:
        return [""]
    draw = ImageDrawForMeasure.instance()
    chunks: list[str] = []
    current = ""
    for char in line:
        trial = current + char
        if draw.text_width(trial, font) <= max_width:
            current = trial
            continue
        if current:
            chunks.append(current)
        current = char
    if current:
        chunks.append(current)
    return chunks


class ImageDrawForMeasure:
    _instance: ImageDrawForMeasure | None = None

    def __init__(self) -> None:
        from PIL import Image, ImageDraw

        self._draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    @classmethod
    def instance(cls) -> ImageDrawForMeasure:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def text_width(self, text: str, font: Any) -> int:
        left, _, right, _ = self._draw.textbbox((0, 0), text, font=font)
        return right - left


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=default_database_path())
    parser.add_argument("--role", action="append", default=["AI应用工程师"])
    parser.add_argument("--city", action="append", default=["上海", "深圳"])
    parser.add_argument("--salary-min-k", type=int, default=20)
    parser.add_argument("--experience-max-years", type=int, default=3)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--refresh-mode",
        choices=("fast", "full", "cache"),
        default="full",
    )
    parser.add_argument("--allow-browser-sources", action="store_true", default=True)
    parser.add_argument("--include-seen", action="store_true", default=True)
    parser.add_argument("--use-profile", action="store_true", default=True)
    parser.add_argument("--reports-dir", type=Path, default=REPORT_DIR)
    parser.add_argument(
        "--asset",
        type=Path,
        default=REPORT_DIR / "latest_search.png",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    core = jobfindsmecore(args.db)
    registry = ToolRegistry(core)

    doctor = Doctor(args.db).run()
    config_response = registry.call(
        "setup",
        {
            "name": "Real World Smoke",
            "target_roles": tuple(args.role),
            "locations": tuple(args.city),
            "salary_min_k": args.salary_min_k,
            "experience_max_years": args.experience_max_years,
            "recruitment_track": RecruitmentTrack.SOCIAL.value,
            "employment_type": EmploymentType.FULL_TIME.value,
        },
    )
    configure_ok = config_response.get("isError") is False
    result = core.search_jobs_with_diagnostics(
        limit=args.limit,
        allow_browser_sources=args.allow_browser_sources,
        refresh_mode=SearchRefreshMode(args.refresh_mode),
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
            "target_roles": args.role,
            "locations": args.city,
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
        "sources": _source_rows(result.diagnostics.source_runs, top_counts),
        "top_counts": top_counts,
        "smoke": {
            "doctor_ok": doctor.ok,
            "configure_ok": configure_ok,
            "search_ok": mcp_search.get("isError") is False,
            "sections_present": all(f"【{index}·" in mcp_text for index in range(1, 6)),
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
    _write_terminal_asset(
        args.asset,
        (
            "用 jobfindsme，根据本地简历，找上海和深圳的 "
            "AI 应用工程师，20K以上，社招，正式。"
        ),
        final_text,
    )
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "asset": str(args.asset),
                "ok": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
