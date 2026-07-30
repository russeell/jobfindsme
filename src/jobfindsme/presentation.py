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


def format_job_list(items: Sequence[Any]) -> str:
    """Render stable, evidence-based recommendation blocks."""
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
        if score is not None:
            fields.append(f"匹配度 {round(score * 100)}%")
        lines = ["｜".join(fields)]
        reasons = tuple(getattr(evidence, "reasons", ())) if evidence else ()
        warnings = tuple(getattr(evidence, "warnings", ())) if evidence else ()
        if reasons:
            lines.append("推荐理由：" + "；".join(reasons[:3]))
        if warnings:
            lines.append("注意事项：" + "；".join(warnings[:2]))
        lines.append(f"   投递链接：{job.apply_url}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_search_results(items: Sequence[Any], changes: SearchChanges) -> str:
    labels = []
    for label, count in (
        ("新增", changes.new),
        ("变更", changes.changed),
        ("重开", changes.reopened),
        ("关闭", changes.closed),
    ):
        if count:
            labels.append(f"{label} {count}")
    summary = "本轮变化：" + ("，".join(labels) if labels else "无")
    if changes.repeated_suppressed:
        summary += f"；已隐藏重复 {changes.repeated_suppressed}"
    return summary + "\n\n" + format_job_list(items)


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
