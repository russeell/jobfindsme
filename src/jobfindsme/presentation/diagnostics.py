"""Source-status lines and safe error classification.

Chrome/CDP errors are sanitised to a single recovery message so the
user (and the host model) never sees raw commands, port numbers, or
stack traces.
"""

from __future__ import annotations

from jobfindsme.contracts import (
    SearchRefreshMode,
    SearchRunDiagnostics,
    SourceRunStatus,
)


def _source_line(diagnostics: SearchRunDiagnostics) -> str:
    source_parts = []
    for run in diagnostics.source_runs:
        if run.status in {SourceRunStatus.SUCCESS, SourceRunStatus.DEGRADED}:
            marker = "✓" if run.status is SourceRunStatus.SUCCESS else "△"
            suffix = "·缓存" if run.cache_used else ""
            source_parts.append(f"{run.source_name} {marker}({run.discovered}{suffix})")
        elif run.status is SourceRunStatus.FAILED:
            source_parts.append(f"{run.source_name} ✗({_short_error(run.error)})")
        else:
            source_parts.append(f"{run.source_name} -({_short_error(run.error)})")
    return "检索：" + (" · ".join(source_parts) if source_parts else "本地缓存")


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
    if diagnostics.refresh_mode is SearchRefreshMode.CACHE:
        return source_line + (
            f"\n本轮未刷新外部来源，从本地缓存匹配到 {diagnostics.result_count} 条。"
        )
    return source_line + (
        f"\n本轮远程发现 {diagnostics.total_discovered} 条，"
        f"本地岗位库匹配到 {diagnostics.result_count} 条。"
    )
