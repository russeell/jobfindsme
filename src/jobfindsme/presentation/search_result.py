"""The five-section search result contract (①-⑤).

This text IS the deterministic Agent contract: every host receives the
identical ordered sections.  Hosts MUST return it verbatim — never
renumber, delete, reorder, or rewrite blocks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jobfindsme.contracts import (
    SearchChanges,
    SearchPresentationContext,
    SearchRunDiagnostics,
    SourceRunStatus,
)
from jobfindsme.presentation.diagnostics import _run_count_line, _source_line
from jobfindsme.presentation.job_block import format_job_list


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
    changes_line = (
        f"本次新增 {changes.new} 个，变更 {changes.changed} 个，"
        f"重开 {changes.reopened} 个，关闭 {changes.closed} 个。"
    )
    if changes.repeated_suppressed:
        changes_line += (
            f"已隐藏 {changes.repeated_suppressed} 个此前展示且未变化的岗位。"
        )
    return "\n\n".join(
        (
            "【1·简历解析】\n" + profile_line,
            "【2·检索概览】\n" + source_line,
            "【3·过滤说明】\n" + filter_line,
            "【4·岗位列表】\n" + job_text,
            "【5·说明】\n" + changes_line,
        )
    )


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
