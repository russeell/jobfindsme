from __future__ import annotations

import re
from datetime import UTC, datetime

from jobfindsme.contracts import SuggestedPlan
from jobfindsme.profiles.models import FactType, ProfileSummary
from jobfindsme.taxonomy import (
    AI_ROLE_SIGNALS,
    LOCATION_ALIASES,
    TECHNICAL_ROLE_MARKERS,
)

_BACKEND_SIGNALS = (
    "java",
    "spring",
    "go",
    "golang",
    "mysql",
    "postgres",
    "redis",
    "docker",
    "kubernetes",
    "k8s",
    "后端",
    "服务端",
    "backend",
)
_ALGORITHM_SIGNALS = (
    "机器学习",
    "深度学习",
    "pytorch",
    "tensorflow",
    "算法",
    "训练",
    "模型优化",
)


def suggest_search_plan(summary: ProfileSummary | None) -> SuggestedPlan:
    """Build an evidence-bound proposal; never persist inferred preferences."""
    if summary is None:
        return SuggestedPlan(
            target_roles=(),
            ready=False,
            reasoning="尚未确认简历。请先调用 setup 导入并确认简历。",
        )

    facts = list(summary.facts)
    skill_values = [
        fact.value.casefold() for fact in facts if fact.fact_type is FactType.SKILL
    ]
    corpus = " ".join(
        value
        for fact in facts
        for value in (fact.value, fact.evidence_snippet)
        if value
    ).casefold()

    ai_count = _count_signals(AI_ROLE_SIGNALS, corpus, skill_values)
    backend_count = _count_signals(_BACKEND_SIGNALS, corpus, skill_values)
    algorithm_count = _count_signals(_ALGORITHM_SIGNALS, corpus, skill_values)
    technical = any(marker in corpus for marker in TECHNICAL_ROLE_MARKERS)
    target_roles, role_reason = _suggest_roles(
        ai_count=ai_count,
        backend_count=backend_count,
        algorithm_count=algorithm_count,
        technical=technical,
    )
    locations = _historical_locations(corpus)
    location_reason = (
        f"从简历中检测到历史地点：{'、'.join(locations)}，不代表求职偏好"
        if locations
        else "简历中未检测到地点信息，请手动选择城市"
    )
    experience_years = _experience_years(summary)
    experience_reason = (
        f"从经历中估算约{experience_years}年工作经验"
        if experience_years
        else "无法从简历中估算工作年限"
    )
    recruitment_track, employment_type, track_reason = _employment_hint(summary)

    requires_confirmation = ["target_roles", "salary_min_k"]
    if locations:
        requires_confirmation.append("locations")
    if experience_years is not None:
        requires_confirmation.append("experience_max_years")
    if recruitment_track is None:
        requires_confirmation.extend(["recruitment_track", "employment_type"])

    return SuggestedPlan(
        target_roles=target_roles,
        locations=locations,
        salary_min_k=None,
        experience_max_years=experience_years,
        candidate_experience_years=experience_years,
        recruitment_track=recruitment_track,
        employment_type=employment_type,
        confidence="medium" if ai_count >= 2 else "low",
        requires_confirmation=tuple(requires_confirmation),
        reasoning="；".join(
            (
                role_reason,
                location_reason,
                experience_reason,
                "简历未提供可确认的期望薪资，需要用户补充",
                track_reason,
            )
        ),
        ready=True,
    )


def _count_signals(
    signals: tuple[str, ...], corpus: str, skill_values: list[str]
) -> int:
    return sum(
        signal.casefold() in corpus
        or any(signal.casefold() in value for value in skill_values)
        for signal in signals
    )


def _suggest_roles(
    *, ai_count: int, backend_count: int, algorithm_count: int, technical: bool
) -> tuple[tuple[str, ...], str]:
    if ai_count >= 2:
        return ("AI应用工程师",), "简历中包含多个 AI/大模型/Agent 信号"
    if algorithm_count >= 3:
        return ("算法工程师",), "简历以机器学习/深度学习技能为主"
    if backend_count >= 3 and technical:
        return ("后端工程师",), "简历以后端开发技能为主"
    if technical:
        return (
            ("AI应用工程师", "后端工程师"),
            "检测到技术岗位信号但方向不够明确，建议选择其一",
        )
    return ("AI应用工程师",), "默认方向，请根据实际情况调整"


def _historical_locations(corpus: str) -> tuple[str, ...]:
    counts = {
        canonical: sum(
            corpus.count(alias.casefold()) for alias in (canonical, *aliases)
        )
        for canonical, aliases in LOCATION_ALIASES.items()
        if canonical != "中国"
    }
    return tuple(
        city
        for city, count in sorted(counts.items(), key=lambda item: -item[1])
        if count
    )[:3]


def _experience_years(summary: ProfileSummary) -> int | None:
    ranges: list[tuple[int, int]] = []
    explicit: list[int] = []
    for fact in summary.facts:
        if fact.fact_type is not FactType.EXPERIENCE:
            continue
        explicit.extend(
            int(match.group(1))
            for match in re.finditer(r"(?<!\d)(\d{1,2})\s*年", fact.value)
        )
        for match in re.finditer(
            r"((?:19|20)\d{2})[./年-]\d{1,2}"
            r".{0,12}?"
            r"(?:((?:19|20)\d{2})[./年-]\d{1,2}|至今|现在|present)",
            fact.value,
            re.I,
        ):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else datetime.now(UTC).year
            if 1990 <= start <= 2030 and 1990 <= end <= 2030:
                ranges.append((start, end))

    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    ranged_years = sum(end - start for start, end in merged)
    return ranged_years or max(explicit, default=0) or None


def _employment_hint(
    summary: ProfileSummary,
) -> tuple[str | None, str | None, str]:
    experience = " ".join(
        fact.value for fact in summary.facts if fact.fact_type is FactType.EXPERIENCE
    ).casefold()
    education = " ".join(
        fact.value for fact in summary.facts if fact.fact_type is FactType.EDUCATION
    ).casefold()
    student = any(
        marker in f"{experience} {education}"
        for marker in ("在读", "应届", "毕业生", "实习")
    )
    non_intern_experience = bool(experience) and "实习" not in experience
    if student and not non_intern_experience:
        return (
            "campus",
            "internship" if "实习" in experience else None,
            "简历含应届、在读或实习信号",
        )
    if non_intern_experience:
        return "social", "full_time", "简历含非实习工作经历"
    return None, None, "无法可靠判断校招/社招与岗位性质"
