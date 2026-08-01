"""Per-job blocks: facts, match result, signals, apply link, reason.

Every block is generated ONLY from structured evidence (job fields +
extracted signals).  Never add subjective evaluations — company
reputation, area desirability, industry outlook, benefits.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jobfindsme.contracts import (
    EmploymentType,
    JobMatch,
    JobSummary,
    RecruitmentTrack,
)
from jobfindsme.presentation.salary import _has_disclosed_salary

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

        # Structured signals support deterministic reasons and optional host UI.
        signals = _extracted_signals(evidence)
        has_jd_signals = _has_extractable_signals(signals)

        # Match degree = deterministic signal score; shown only when a
        # confirmed profile exists (score_signals returns 0 without one).
        if score and score > 0:
            if has_jd_signals:
                lines.append(
                    f"   匹配度：{round(score * 100)}%（信号匹配，非录用概率）"
                )
            else:
                lines.append(
                    "   匹配度：已通过角色、地点、薪资等可判定硬条件；"
                    "JD 信息有限，未给出信号百分比"
                )
        elif include_recommendation:
            lines.append(
                "   匹配度：已通过角色、地点、薪资等可判定硬条件（非录用概率）"
            )

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
                        evidence=evidence,
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
    evidence: Any | None,
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
    matched = list(getattr(evidence, "matched_profile_skills", ())) if evidence else []
    missing = list(getattr(evidence, "missing_required_skills", ())) if evidence else []
    has_jd_signals = _has_extractable_signals(signals)
    if matched:
        parts.append("简历技能命中：" + "、".join(matched[:6]))
    if missing:
        parts.append("岗位要求但简历未体现：" + "、".join(missing[:6]))
    if profile_used and score is not None and has_jd_signals:
        parts.append(f"简历事实与岗位信号综合匹配度为 {round(score * 100)}%")
    elif profile_used:
        parts.append("JD 信息有限，未给出信号百分比")
    else:
        parts.append("岗位名称已通过目标角色筛选（本次未使用简历，按明确条件匹配）")
    skills = signals.get("required_skills") or []
    if skills:
        parts.append("JD 明确涉及 " + "、".join(skills[:4]))
    if _has_disclosed_salary(job):
        parts.append("薪资信息明确")
    return "；".join(parts) + "。"


def _has_extractable_signals(signals: dict) -> bool:
    """True when the JD yielded at least one structured signal for display."""
    return bool(
        signals.get("required_skills")
        or signals.get("required_experience")
        or signals.get("required_degree")
    )
