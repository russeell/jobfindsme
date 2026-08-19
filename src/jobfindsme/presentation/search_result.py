"""The five-section factual baseline (①-⑤) and source diagnostics.

This text is the Server's compact factual summary. The host Agent organizes
the final user-facing expression from the returned facts; it must not
contradict this baseline or invent facts.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

from jobfindsme.contracts import (
    SearchChanges,
    SearchPresentationContext,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SourceRunStatus,
)
from jobfindsme.presentation.job_block import (
    _job_score_and_evidence,
    format_job_list,
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


def format_search_results(
    items: Sequence[Any],
    changes: SearchChanges,
    diagnostics: SearchRunDiagnostics,
    context: SearchPresentationContext,
) -> str:
    profile_line = (
        f"简历解析：技能 {context.skill_count} 项 ｜ "
        f"项目 {context.project_count} 项 ｜ "
        f"经验 {context.experience_count} 项 ｜ "
        f"学历：{context.highest_degree or '未识别'}"
        if context.profile_used
        else "简历解析：本次未使用简历，按用户明确条件匹配。"
    )
    source_line = _run_count_line(diagnostics, source_line=_source_line(diagnostics))
    filters = " + ".join(context.applied_filters) or "未设置额外条件"
    filter_line = f"过滤：{filters} → 给出 {diagnostics.result_count} 个"
    if diagnostics.undisclosed_salary_filtered_count:
        filter_line += (
            f"；另有 {diagnostics.undisclosed_salary_filtered_count} 个"
            "薪资未公开岗位按严格模式排除"
        )
    if diagnostics.undisclosed_salary_included_count:
        filter_line += (
            f"；保留 {diagnostics.undisclosed_salary_included_count} 个"
            "薪资未公开岗位并逐条提示"
        )
    job_text = format_job_list(
        items,
        include_recommendation=True,
        profile_used=context.profile_used,
    )
    if not items:
        job_text = format_search_empty(diagnostics)
    return "\n\n".join(
        (
            "【1·简历解析】\n" + profile_line,
            "【2·检索概览】\n" + source_line,
            "【3·过滤说明】\n" + filter_line,
            "【4·岗位列表】\n" + job_text,
            "【5·说明】\n" + _operating_summary(items, changes, diagnostics, context),
        )
    )


def _operating_summary(
    items: Sequence[Any],
    changes: SearchChanges,
    diagnostics: SearchRunDiagnostics,
    context: SearchPresentationContext,
) -> str:
    """Render ⑤: results, apply suggestions, next steps, source notes."""
    lines = [
        _result_summary(changes, diagnostics, context),
        _priority_suggestions(items),
        "下一步建议（和 AI 聊天就能用）：",
        "- 📬 定时推送：对我说「每天早上 9 点推送新岗位给我」（可改任意时间频率）",
        "- 📋 查看历史：对我说「我投过哪些岗位？」或「我之前看过的岗位有哪些？」",
    ]
    note = _source_note(diagnostics, changes)
    if note:
        lines.append(note)
    lines.append(_apply_tip(items))
    return "\n".join(lines)


def _result_summary(
    changes: SearchChanges,
    diagnostics: SearchRunDiagnostics,
    context: SearchPresentationContext,
) -> str:
    """结果 line: shown this round, cumulative shows, closed jobs."""
    count = diagnostics.result_count
    if count > 0 and changes.new == count:
        desc = "全部新增"
    elif count > 0:
        desc = (
            f"含新增 {changes.new} 条、变更 {changes.changed} 条、"
            f"重开 {changes.reopened} 条"
        )
    else:
        desc = "无新增"
    line = (
        f"结果：历史共匹配 {context.total_matched_count} 个合适岗位；"
        f"本次展示 {count} 个（{desc}）；累计展示 {context.cumulative_shown_count} 次；"
        f"另有 {context.closed_count} 个岗位已关闭（不再推荐）。"
    )
    if changes.repeated_suppressed:
        line += f"重复抑制（此前展示且未变化）{changes.repeated_suppressed} 条。"
    return line


def _priority_suggestions(items: Sequence[Any]) -> str:
    """建议 line: top three jobs with an evidence-backed reason tag."""
    if not items:
        return "建议：当前没有可投递的新岗位；可放宽城市、薪资或经验条件后重试。"
    picks = []
    for index, item in enumerate(items[:3], start=1):
        job, _, evidence, _ = _job_score_and_evidence(item)
        company = job.company or "某公司"
        salary = (
            job.salary.raw_text if job.salary and job.salary.raw_text else "薪资面议"
        )
        matched = (
            list(getattr(evidence, "matched_profile_skills", ())) if evidence else []
        )
        if matched:
            tag = "技能：" + "、".join(matched[:3])
        elif "面议" not in salary:
            tag = "薪资明确"
        else:
            tag = "薪资未注明"
        picks.append(f"#{index}（{company}，{salary}，{tag}）")
    return "建议：优先投 " + " → ".join(picks) + "。"


def _source_note(
    diagnostics: SearchRunDiagnostics,
    changes: SearchChanges,
) -> str | None:
    """来源说明: degraded/failed sources and chat-driven recovery."""
    issues = [
        run
        for run in diagnostics.source_runs
        if run.status in (SourceRunStatus.DEGRADED, SourceRunStatus.FAILED)
    ]
    if not issues:
        return None
    lines = []
    boss_issue = any("BOSS" in run.source_name for run in issues)
    if boss_issue:
        lines.append(
            "BOSS直聘说明：本次 BOSS 刷新未返回新数据"
            "（浏览器桥可能不在线或需重新登录）。"
            "解决方案：对我说「帮我重新登录 BOSS直聘」，或让我运行 jobfindsme setup "
            "确认窗口在线。"
        )
        if any(run.cache_used for run in issues if "BOSS" in run.source_name) and (
            changes.new
        ):
            lines.append(f"本次 {changes.new} 个新增来自缓存岗位，已正常纳入。")
    other = [run.source_name for run in issues if "BOSS" not in run.source_name]
    if other:
        names = "、".join(dict.fromkeys(other))
        lines.append(
            f"{names} 本次刷新未成功，已使用缓存或跳过；"
            "对我说「重新搜索一次」即可重试。"
        )
    return "\n".join(lines)


def _apply_tip(items: Sequence[Any]) -> str:
    if not items:
        return "投递岗位后告诉我，我会记住并跳过已投递岗位。"
    return "投递后对我说「把第 1 个标记为已投递」，明天推送自动跳过它。"


def format_search_empty(diagnostics: SearchRunDiagnostics) -> str:
    """Explain why an incremental search returned no visible jobs."""
    attempted = [
        run
        for run in diagnostics.source_runs
        if run.status is not SourceRunStatus.SKIPPED
    ]
    if attempted and all(run.status is SourceRunStatus.FAILED for run in attempted):
        return "岗位来源刷新失败，未把失败误报成‘没有新岗位’。请稍后重试。"
    if diagnostics.repeated_suppressed_count:
        return (
            "本轮没有新增或变化的合格岗位。"
            f"已隐藏 {diagnostics.repeated_suppressed_count} 个此前展示过的岗位；"
            "需要查看历史结果时，请使用 include_seen=true。"
        )
    return "当前来源或本地缓存中没有符合搜索条件的岗位。"
