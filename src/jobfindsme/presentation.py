"""Stable human-facing job list presentation shared by adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jobfindsme.contracts import (
    EmploymentType,
    JobMatch,
    JobSummary,
    RecruitmentTrack,
    SearchChanges,
    SearchPresentationContext,
    SearchRefreshMode,
    SearchRunDiagnostics,
    SourceRunStatus,
)

_RECRUITMENT_LABELS = {
    RecruitmentTrack.CAMPUS: "校招",
    RecruitmentTrack.SOCIAL: "社招",
    RecruitmentTrack.UNKNOWN: "招聘类型未注明",
}
_EMPLOYMENT_LABELS = {
    EmploymentType.INTERNSHIP: "实习",
    EmploymentType.FULL_TIME: "正式",
    EmploymentType.PART_TIME: "兼职",
    EmploymentType.CONTRACT: "合同",
    EmploymentType.UNKNOWN: "岗位性质未注明",
}


def format_job_list(
    items: Sequence[Any],
    *,
    include_recommendation: bool = False,
    profile_used: bool = False,
) -> str:
    """Render stable, evidence-based recommendation blocks.

    This text is the deterministic part of the Agent contract: every Agent
    receives the identical facts, signals, warnings, link, and base reason.
    Hosts MUST preserve this output verbatim — never renumber, delete,
    reorder, or rewrite blocks, and never add subjective evaluations
    (company reputation, area desirability, industry outlook, benefits) that
    are absent from the returned structured evidence.
    """
    if not items:
        return "未找到符合条件的岗位。"

    blocks = []
    for index, item in enumerate(items, start=1):
        job, score, evidence, change_type = _job_score_and_evidence(item)
        locations = "、".join(job.locations) or "地点未注明"
        fields = [
            f"{index}. {_change_label(change_type)}{job.title}",
            job.company,
            locations,
            _RECRUITMENT_LABELS[job.recruitment_track],
            _EMPLOYMENT_LABELS[job.employment_type],
        ]
        if job.salary and job.salary.raw_text:
            fields.append(job.salary.raw_text)
        lines = ["｜".join(fields)]

        # Match degree = deterministic signal score; shown only when a
        # confirmed profile exists (score_signals returns 0 without one).
        if score and score > 0:
            lines.append(f"   匹配度：{round(score * 100)}%（信号匹配，非录用概率）")
        elif include_recommendation:
            lines.append(
                "   匹配度：已通过角色、地点、薪资等可判定硬条件（非录用概率）"
            )

        # Structured signals support deterministic reasons and optional host UI.
        signals = _extracted_signals(evidence)
        signal_parts = []
        skills = signals.get("required_skills") or []
        if skills:
            signal_parts.append("技能：" + "、".join(skills[:6]))
        if signals.get("required_experience"):
            signal_parts.append(f"经验：{signals['required_experience']}")
        if signals.get("required_degree"):
            signal_parts.append(f"学历：{signals['required_degree']}")
        if signal_parts:
            lines.append("   " + " ｜ ".join(signal_parts))

        warnings = list(getattr(evidence, "warnings", ())) if evidence else []
        if include_recommendation and not _has_disclosed_salary(job):
            warnings.append("薪资未注明")
        if include_recommendation and job.recruitment_track is RecruitmentTrack.UNKNOWN:
            warnings.append("招聘类型未注明")
        if include_recommendation and job.employment_type is EmploymentType.UNKNOWN:
            warnings.append("岗位性质未注明")
        if include_recommendation and warnings:
            lines.append("   需要注意：" + "；".join(dict.fromkeys(warnings[:3])))
        lines.extend(["", f"   投递链接：{job.apply_url}"])
        if include_recommendation:
            lines.extend(
                [
                    "",
                    "   推荐理由："
                    + _recommendation_reason(
                        job,
                        score=score,
                        signals=signals,
                        profile_used=profile_used,
                    ),
                ]
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _extracted_signals(evidence: Any | None) -> dict:
    if evidence is None:
        return {}
    raw = getattr(evidence, "extracted_signals", None)
    if isinstance(raw, dict):
        return raw
    return {}


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
    source_line = "检索：" + (" · ".join(source_parts) if source_parts else "本地缓存")
    if diagnostics.refresh_mode is SearchRefreshMode.CACHE:
        source_line += (
            f"\n本轮未刷新外部来源，从本地缓存匹配到 {diagnostics.result_count} 条。"
        )
    else:
        source_line += (
            f"\n本轮远程发现 {diagnostics.total_discovered} 条，"
            f"本地岗位库匹配到 {diagnostics.result_count} 条。"
        )
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


def _job_score_and_evidence(
    item: Any,
) -> tuple[JobSummary | Any, float | None, Any | None, Any | None]:
    if isinstance(item, JobMatch):
        return item.job, item.score, item.evidence, item.change_type
    if isinstance(item, JobSummary):
        return item, None, None, None
    if isinstance(item, dict):
        job = item.get("job", item)
        score = item.get("score")
        return (
            job,
            float(score) if score is not None else None,
            item.get("evidence"),
            item.get("change_type"),
        )
    return item, None, None, None


def _change_label(change_type: Any | None) -> str:
    labels = {"new": "[新增] ", "changed": "[变更] ", "reopened": "[重开] "}
    value = getattr(change_type, "value", change_type)
    return labels.get(value, "")


def _recommendation_reason(
    job: JobSummary,
    *,
    score: float | None,
    signals: dict,
    profile_used: bool,
) -> str:
    """Build an evidence-grounded recommendation reason.

    CRITICAL: Every claim MUST be backed by structured signals or job
    fields returned by the Server.  Never invent company reputation,
    area desirability, industry outlook, or benefit quality.
    Hosts MUST preserve this reason verbatim — do not append subjective
    evaluations like '龙头', '核心区', '有前景', or '福利齐全'.
    """
    parts = []
    if profile_used and score is not None:
        parts.append(f"简历事实与岗位信号综合匹配度为 {round(score * 100)}%")
    else:
        parts.append("岗位名称已通过目标角色筛选（本次未使用简历，按明确条件匹配）")
    skills = signals.get("required_skills") or []
    if skills:
        parts.append("JD 明确涉及 " + "、".join(skills[:4]))
    if _has_disclosed_salary(job):
        parts.append("薪资信息明确")
    return "；".join(parts) + "。"


def _has_disclosed_salary(job: JobSummary) -> bool:
    """Return whether salary is both numeric and actually disclosed.

    Some source parsers can retain numeric fields while the source card says
    "面议".  The user-facing explanation must follow the source text in that
    conflict instead of claiming that an undisclosed salary is explicit.
    """
    salary = job.salary
    if salary is None or not salary.raw_text.strip():
        return False
    normalized = salary.raw_text.casefold().replace(" ", "")
    undisclosed_markers = ("面议", "未公开", "未注明", "保密", "negotiable")
    if any(marker in normalized for marker in undisclosed_markers):
        return False
    return (
        salary.min_amount is not None
        or salary.max_amount is not None
        or salary.normalized_annual_min is not None
        or salary.normalized_annual_max is not None
    )


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
