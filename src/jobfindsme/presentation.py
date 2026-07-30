"""Stable human-facing job list presentation shared by adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jobfindsme.contracts import (
    EmploymentType,
    JobMatch,
    JobSummary,
    RecruitmentTrack,
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
        job, score, evidence = _job_score_and_evidence(item)
        locations = "、".join(job.locations) or "地点未注明"
        fields = [
            f"{index}. {job.title}",
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


def _job_score_and_evidence(
    item: Any,
) -> tuple[JobSummary | Any, float | None, Any | None]:
    if isinstance(item, JobMatch):
        return item.job, item.score, item.evidence
    if isinstance(item, JobSummary):
        return item, None, None
    if isinstance(item, dict):
        job = item.get("job", item)
        score = item.get("score")
        return (
            job,
            float(score) if score is not None else None,
            item.get("evidence"),
        )
    return item, None, None
