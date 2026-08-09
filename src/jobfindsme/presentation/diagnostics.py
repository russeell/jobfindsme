"""Source-status lines and safe error classification.

Chrome/CDP errors are sanitised to a single recovery message so the
user (and the host model) never sees raw commands, port numbers, or
stack traces.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

from jobfindsme.contracts import (
    SearchRefreshMode,
    SearchRunDiagnostics,
    SourceRunStatus,
)

_PLATFORM_ORDER = {
    "BOSS直聘": 0,
    "猎聘": 1,
    "智联招聘": 2,
    "前程无忧": 3,
}


def _value(run: Any, name: str, default: Any = None) -> Any:
    if isinstance(run, Mapping):
        return run.get(name, default)
    return getattr(run, name, default)


def _source_identity(source_name: str) -> tuple[str, str | None]:
    family, separator, location = source_name.partition("·")
    aliases = {
        "BOSS": "BOSS直聘",
        "BOSS直聘": "BOSS直聘",
        "猎聘": "猎聘",
        "智联": "智联招聘",
        "智联招聘": "智联招聘",
        "51job": "前程无忧",
        "前程无忧": "前程无忧",
    }
    return aliases.get(family, family), location if separator else None


def _status_value(run: Any) -> str:
    status = _value(run, "status", SourceRunStatus.SKIPPED)
    return status.value if hasattr(status, "value") else str(status)


def _source_line_from_runs(source_runs: Sequence[Any]) -> str:
    """Aggregate internal attempts into one readable entry per platform.

    A search plan commonly has one source per city and may also try more than
    one transport strategy. Those are useful diagnostics, but exposing every
    attempt makes the user see repeated platform names. This renderer keeps
    the detail in diagnostics while presenting one concise platform summary.
    """
    grouped: OrderedDict[str, list[Any]] = OrderedDict()
    for run in source_runs:
        family, _ = _source_identity(str(_value(run, "source_name", "未知来源")))
        grouped.setdefault(family, []).append(run)

    families = sorted(
        grouped,
        key=lambda name: (_PLATFORM_ORDER.get(name, 99), list(grouped).index(name)),
    )
    parts: list[str] = []
    for family in families:
        runs = grouped[family]
        locations: OrderedDict[str, list[Any]] = OrderedDict()
        for run in runs:
            _, location = _source_identity(str(_value(run, "source_name", family)))
            locations.setdefault(location or "", []).append(run)

        location_counts: list[tuple[str, int]] = []
        for location, attempts in locations.items():
            count = max(int(_value(item, "discovered", 0) or 0) for item in attempts)
            if location and count:
                location_counts.append((location, count))
        discovered = sum(count for _, count in location_counts)
        if not location_counts:
            discovered = max(
                (int(_value(item, "discovered", 0) or 0) for item in runs),
                default=0,
            )

        statuses = {_status_value(item) for item in runs}
        cache_used = any(bool(_value(item, "cache_used", False)) for item in runs)
        fully_live = statuses == {SourceRunStatus.SUCCESS.value} and not cache_used
        has_live_data = discovered > 0

        if has_live_data:
            marker = "✓" if fully_live else "△"
            detail = str(discovered)
            if len(location_counts) > 1:
                cities = "、".join(
                    f"{location}{count}" for location, count in location_counts
                )
                detail += f"（{cities}）"
            if cache_used:
                detail += " + 缓存"
        elif cache_used:
            marker, detail = "△", "缓存"
        elif statuses == {SourceRunStatus.FAILED.value}:
            marker = "✗"
            detail = _short_error(str(_value(runs[0], "error", "") or ""))
        else:
            marker, detail = "-", "未刷新"
        parts.append(f"{family} {marker} {detail}")
    return "检索：" + (" · ".join(parts) if parts else "本地缓存")


def _coverage_counts(source_runs: Sequence[Any]) -> tuple[int, int]:
    platforms: set[str] = set()
    targets: set[tuple[str, str]] = set()
    for run in source_runs:
        family, location = _source_identity(str(_value(run, "source_name", "未知来源")))
        platforms.add(family)
        targets.add((family, location or "默认"))
    return len(platforms), len(targets)


def _source_line(diagnostics: SearchRunDiagnostics) -> str:
    return _source_line_from_runs(diagnostics.source_runs)


def _short_error(error: str | None) -> str:
    """Normalize source-run errors to safe, short categories.

    Chrome/CDP/9222 errors are unified to a single recovery message so the
    user never sees raw commands, port numbers, or stack traces.  Other
    errors are classified into short safe labels.
    """
    if not error:
        return "无结果"
    lowered = error.lower()
    chrome_markers = (
        "chrome",
        "cdp",
        "9222",
        "remote-debugging-port",
        "chrome-debug",
        "devtools",
        "websocket",
    )
    if any(marker in lowered for marker in chrome_markers):
        return "Chrome 未连接，请运行 jobfindsme setup"
    if "timeout" in lowered or "timed out" in lowered:
        return "来源响应超时"
    if "connection" in lowered or "refused" in lowered or "unreachable" in lowered:
        return "来源无法连接"
    if "auth" in lowered or "login" in lowered or "未登录" in lowered:
        return "来源需要登录"
    if "parse" in lowered or "json" in lowered or "decode" in lowered:
        return "来源返回数据无法解析"
    return error.replace("\n", " ")[:60]


def _run_count_line(
    diagnostics: SearchRunDiagnostics,
    *,
    source_line: str,
) -> str:
    """Compose the section-② lines (source line + refresh summary)."""
    platform_count, target_count = _coverage_counts(diagnostics.source_runs)
    coverage = (
        f"覆盖 {platform_count} 个平台、{target_count} 个城市来源；"
        if platform_count
        else ""
    )
    if diagnostics.refresh_mode is SearchRefreshMode.CACHE:
        return source_line + (
            f"\n{coverage}本轮未刷新外部来源，从本地缓存匹配到 "
            f"{diagnostics.result_count} 条。"
        )
    return source_line + (
        f"\n{coverage}本轮远程发现 {diagnostics.total_discovered} 条，"
        f"本地岗位库匹配到 {diagnostics.result_count} 条。"
    )
