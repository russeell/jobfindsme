"""Evidence-only desktop v2 scoring. Model prose never supplies these scores."""

from __future__ import annotations

import re
from datetime import date

from jobfindsme.taxonomy import extract_skills

DEFAULT_WEIGHTS = {"skills": 35, "projects": 30, "education": 15, "experience": 20}
DEGREES = [
    (4, r"博士|\bph\.?d\b|doctorate"),
    (3, r"硕士|研究生|master"),
    (2, r"本科|学士|bachelor"),
    (1, r"大专|专科|associate"),
]


def degree(text: str, *, minimum: bool = False) -> int | None:
    found = [level for level, pattern in DEGREES if re.search(pattern, text, re.I)]
    return (min(found) if minimum else max(found)) if found else None


def work_years(lines: list[str] | tuple[str, ...]) -> float | None:
    lines = [line for line in lines if not re.search(r"实习|intern", line, re.I)]
    text = " ".join(lines)
    # Only explicit work tenure, never age, graduation year or project duration.
    explicit = re.findall(
        r"(?:工作经验|工作年限|累计工作)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*年|(\d+(?:\.\d+)?)\s*年(?:以上)?(?:的)?(?:工作经验|工作经历)",
        text,
    )
    if explicit:
        return max(float(a or b) for a, b in explicit)
    months: set[int] = set()
    today = date.today()
    for line in lines:
        if "实习" in line or re.search(r"intern", line, re.I):
            continue
        for match in re.finditer(
            r"(20\d{2})[./年-](\d{1,2})月?\s*(?:—|–|-|~|至|到)\s*(?:(20\d{2})[./年-](\d{1,2})月?|(至今|现在|present))",
            line,
            re.I,
        ):
            y, m, end_y, end_m, current = match.groups()
            start = int(y) * 12 + int(m) - 1
            end = (
                today.year * 12 + today.month - 1
                if current
                else int(end_y) * 12 + int(end_m) - 1
            )
            if (
                1 <= int(m) <= 12
                and (current or 1 <= int(end_m) <= 12)
                and start <= end <= today.year * 12 + today.month - 1
            ):
                months.update(range(start, end))
    return len(months) / 12 if months else None


def evaluate(job, resume_version, weights: dict[str, int]) -> dict:
    content = resume_version.content if resume_version else {}
    jd = job.description
    job_skills = set(extract_skills(jd))
    resume_skills = {
        s
        for section in ("skills", "projects", "experience")
        for line in content.get(section, ())
        for s in extract_skills(line)
    }
    details = {}

    def put(key, ratio, known, explanation):
        details[key] = {
            "weight": weights[key],
            "ratio": round(ratio, 4),
            "points": round(ratio * weights[key], 2),
            "status": "known" if known else "unknown",
            "explanation": explanation,
        }

    matched = sorted(job_skills & resume_skills)
    known = bool(
        job_skills
        and resume_version
        and any(content.get(s) for s in ("skills", "projects", "experience"))
    )
    put(
        "skills",
        len(matched) / len(job_skills) if known else 0,
        known,
        (
            f"JD技能{len(job_skills)}项，简历证据匹配{len(matched)}项："
            f"{' / '.join(matched) or '无'}。"
        )
        if known
        else "JD技能或已确认简历证据不足，暂不计分。",
    )

    # A project needs an action/contribution, not just a bare list of skills.
    projects = content.get("projects", ())
    evidence = [
        line
        for line in projects
        if re.search(
            r"开发|实现|搭建|设计|负责|构建|优化|部署|上线|完成|built|implemented|developed|designed|deployed",
            line,
            re.I,
        )
    ]
    project_skills = {s for line in evidence for s in extract_skills(line)}
    project_matches = sorted(job_skills & project_skills)
    known = bool(job_skills and projects)
    put(
        "projects",
        len(project_matches) / len(job_skills) if known else 0,
        known,
        f"{len(evidence)}条有行动描述的项目证据，覆盖JD技能{len(project_matches)}/{len(job_skills)}项；仅列关键词不计作项目经历。"
        if known
        else "缺少项目经历或可对应的JD技能，暂不计分。",
    )

    requirement = degree(
        " ".join(
            line
            for line in re.split(r"[。；;\n]", jd)
            if re.search(r"学历|学位|及以上|及以上学历|degree|required", line, re.I)
        ),
        minimum=True,
    )
    education = content.get("education", ())
    attained = degree(
        " ".join(
            line
            for line in education
            if not re.search(
                r"在读|预计|预期|肄业|candidate|expected|pursuing", line, re.I
            )
        )
    )
    unrestricted = bool(re.search(r"学历不限|不限学历|no degree required", jd, re.I))
    known = bool(
        resume_version
        and (unrestricted or requirement is not None and attained is not None)
    )
    ratio = 1 if known and (unrestricted or attained >= requirement) else 0
    put(
        "education",
        ratio,
        known,
        "JD明确不限学历。"
        if known and unrestricted
        else "已确认学历满足JD最低要求。"
        if ratio
        else "已确认学历低于JD最低要求。"
        if known
        else "JD最低学历或简历已取得学历未知，暂不计分。",
    )

    required = job.experience_min_years
    if required is None:
        match = re.search(
            r"(\d+)\s*(?:[-~—至]\s*\d+\s*)?年(?:及以上|以上)?(?:的)?(?:相关)?(?:工作|开发|行业)?经验",
            jd,
        )
        if match:
            required = int(match.group(1))
        elif re.search(r"经验不限|不限经验|无需工作经验", jd):
            required = 0
    years = work_years(content.get("experience", ()))
    known = bool(
        resume_version and required is not None and (required == 0 or years is not None)
    )
    ratio = (1 if required == 0 else min(1, years / required)) if known else 0
    put(
        "experience",
        ratio,
        known,
        "JD明确无需工作经验。"
        if known and required == 0
        else f"可确认工作年限{years:.1f}年 / JD最低{required}年，按达成比例计分。"
        if known
        else "JD年限或简历工作年限未知，暂不计分；不从年龄推算。",
    )
    components = {key: value["points"] for key, value in details.items()}
    return {
        "score": round(sum(components.values()), 2),
        "components": components,
        "coverage": round(
            sum(v["weight"] for v in details.values() if v["status"] == "known") / 100,
            2,
        ),
        "details": details,
        "scoring_version": "desktop-v2",
    }
