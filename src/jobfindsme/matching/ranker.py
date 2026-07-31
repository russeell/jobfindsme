"""Job filtering — hard constraints only, no subjective scoring.

Since v0.4 the matcher no longer produces BM25 scores.  The Agent
owns semantic understanding and ranking; the MCP Server provides
hard-filtered, structured data for the Agent to work with.

``DeterministicMatcher`` is kept for backward compatibility with the
evaluation pipeline only.  New code should use ``filter_jobs``.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from jobfindsme.contracts import (
    EmploymentType,
    EvidencePair,
    JobLiveness,
    JobMatch,
    JobPosting,
    MatchEvidence,
    RecruitmentTrack,
    SearchPlan,
)
from jobfindsme.matching.tokenizer import tokenize
from jobfindsme.profiles.models import FactType, ProfileSummary
from jobfindsme.taxonomy import (
    expand_location_terms,
    expand_role_terms,
    extract_required_skills,
    extract_skills,
    is_target_role_candidate,
)


class DeterministicMatcher:
    """Legacy matcher — kept for evaluation backward compatibility only.

    New code should use the module-level ``filter_jobs`` and
    ``extract_job_signals`` functions instead.
    """

    stale_after_days: int | None = None

    def match(self, *args, **kwargs):
        """Delegates to module-level ``_legacy_match``."""
        return _legacy_match(*args, **kwargs)

    def eligible_count(
        self,
        plan: SearchPlan,
        jobs: list[JobPosting],
    ) -> int:
        """Count jobs that pass hard filters (used for diagnostics)."""
        return sum(
            1 for job in jobs if _hard_filter(plan, job, stale_after_days=self.stale_after_days)
        )

    @staticmethod
    def _hard_filter(
        plan: SearchPlan,
        job: JobPosting,
        *,
        stale_after_days: int | None = None,
    ) -> bool:
        return _hard_filter(plan, job, stale_after_days=stale_after_days)


# ── Public API ────────────────────────────────────────────────────────────────


def filter_jobs(
    plan: SearchPlan,
    jobs: list[JobPosting],
    *,
    limit: int = 50,
    stale_after_days: int | None = 7,
) -> list[JobPosting]:
    """Return jobs that pass all hard filters, in natural order.

    No scoring, no ranking.  The calling Agent is responsible for
    semantic matching, ordering, and explanation.
    """
    eligible = [
        job
        for job in jobs
        if _hard_filter(plan, job, stale_after_days=stale_after_days)
    ]
    return eligible[:limit]


def extract_job_signals(job: JobPosting) -> dict:
    """Extract structured signals from a job posting for Agent-side matching.

    Returns a dict with:
      - required_skills: list[str]  — canonical skill names found in the JD
      - required_experience: str    — e.g. \"3-5年\" or \"\"
      - required_degree: str        — e.g. \"本科\" or \"\"
      - employment_type: str        — detected employment type
      - recruitment_track: str      — detected recruitment track
      - liveness: str               — active / stale / closed / unknown
      - salary_range: str           — e.g. \"30K-50K\" or \"\"
    """
    text = f"{job.title} {job.description}".casefold()

    # Skills from taxonomy
    required_skills = sorted(set(extract_skills(text)))

    # Experience
    exp_match = re.search(r"(\d+[-~]\d+)\s*年", text)
    required_experience = exp_match.group(0) if exp_match else ""

    # Degree
    degree_map = {
        "博士": "博士",
        "硕士": "硕士",
        "本科": "本科",
        "大专": "大专",
        "学历不限": "不限",
    }
    required_degree = ""
    for key, val in degree_map.items():
        if key in text:
            required_degree = val
            break

    # Employment type
    if "实习" in text or "intern" in text:
        employment_type = "internship"
    elif "兼职" in text:
        employment_type = "part_time"
    else:
        employment_type = "full_time"

    # Recruitment track
    if any(t in text for t in ("校招", "校园", "应届", "2027届", "2026届")):
        recruitment_track = "campus"
    else:
        recruitment_track = "social"

    return {
        "required_skills": required_skills,
        "required_experience": required_experience,
        "required_degree": required_degree,
        "employment_type": employment_type,
        "recruitment_track": recruitment_track,
        "liveness": job.source.liveness.value if job.source.liveness else "unknown",
        "salary_range": (
            f"{job.salary_min_k}K-{job.salary_max_k}K" if job.salary_min_k else ""
        ),
    }


# ── Hard filter (unchanged from previous version) ─────────────────────────────


def _hard_filter(
    plan: SearchPlan,
    job: JobPosting,
    *,
    stale_after_days: int | None = None,
) -> bool:
    if job.source.liveness in {JobLiveness.CLOSED, JobLiveness.STALE}:
        return False
    if (
        stale_after_days is not None
        and job.source.liveness is JobLiveness.UNKNOWN
        and job.source.fetched_at is not None
        and (datetime.now(UTC) - job.source.fetched_at).days > stale_after_days
    ):
        return False
    if (
        plan.recruitment_track is not None
        and plan.recruitment_track is not RecruitmentTrack.UNKNOWN
        and job.recruitment_track is not plan.recruitment_track
    ):
        return False
    if (
        plan.employment_type is not None
        and plan.employment_type is not EmploymentType.UNKNOWN
        and job.employment_type is not plan.employment_type
    ):
        return False
    searchable = f"{job.title} {job.description} {' '.join(job.locations)}".casefold()
    if any(term.casefold() in searchable for term in plan.exclusions):
        return False
    if not is_target_role_candidate(
        job.title,
        job.description,
        plan.target_roles,
    ):
        return False
    if plan.experience_max_years is not None and plan.experience_max_years <= 3:
        senior_markers = (
            "资深",
            "高级",
            "专家",
            "senior",
            "staff",
            "principal",
            "lead",
        )
        if any(marker in job.title.casefold() for marker in senior_markers):
            return False
    location_terms = expand_location_terms(plan.locations)
    if location_terms and not any(
        location.casefold() in searchable for location in location_terms
    ):
        return False
    if (
        plan.salary_min_k is not None
        and _annual_salary_min(job) is not None
        and _annual_salary_min(job) < plan.salary_min_k * 1000 * 12
    ):
        return False
    if (
        plan.salary_max_k is not None
        and _annual_salary_min(job) is not None
        and _annual_salary_min(job) > plan.salary_max_k * 1000 * 12
    ):
        return False
    return not (
        plan.experience_max_years is not None
        and job.experience_min_years is not None
        and job.experience_min_years > plan.experience_max_years
    )


# ── Legacy BM25 scoring (kept for evaluation backward compat) ─────────────────

import math  # noqa: E402


def _legacy_match(
    plan: SearchPlan,
    jobs: list[JobPosting],
    *,
    profile: ProfileSummary | None = None,
    limit: int = 20,
    min_score: float = 0.10,
    stale_after_days: int | None = None,
) -> list[JobMatch]:
    """BM25-based matching — for evaluation use only."""
    effective_stale = stale_after_days
    eligible = [
        job for job in jobs if _hard_filter(plan, job, stale_after_days=effective_stale)
    ]
    if not eligible:
        return []
    query_terms = tokenize(" ".join(expand_role_terms(plan.target_roles)))
    profile_facts = profile.facts if profile else ()
    profile_skill_evidence = {
        skill: fact.evidence_snippet
        for fact in profile_facts
        if fact.fact_type is FactType.SKILL
        for skill in extract_skills(fact.value)
    }
    profile_experience = _profile_experience_years(profile)
    documents = [tokenize(f"{job.title} {job.description}") for job in eligible]
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    matches = [
        _bm25_score(
            plan,
            job,
            terms,
            query_terms,
            document_frequency,
            len(eligible),
            profile_skill_evidence,
            profile_experience,
        )
        for job, terms in zip(eligible, documents, strict=True)
    ]
    scored = [m for m in matches if m.score >= min_score]
    return sorted(scored, key=lambda item: (-item.score, item.job.job_id))[:limit]


def _bm25_score(
    plan: SearchPlan,
    job: JobPosting,
    document: tuple[str, ...],
    query: tuple[str, ...],
    document_frequency: Counter[str],
    document_count: int,
    profile_skill_evidence: dict[str, str],
    profile_experience: int | None,
) -> JobMatch:
    frequencies = Counter(document)
    bm25 = 0.0
    matched: list[str] = []
    for term in dict.fromkeys(query):
        frequency = frequencies[term]
        if not frequency:
            continue
        matched.append(term)
        inverse_frequency = math.log(
            1
            + (document_count - document_frequency[term] + 0.5)
            / (document_frequency[term] + 0.5)
        )
        bm25 += inverse_frequency * frequency / (frequency + 1.2)
    title_bonus = (
        0.25
        if any(role.casefold() in job.title.casefold() for role in plan.target_roles)
        else 0.0
    )
    location_bonus = (
        0.1
        if plan.locations
        and any(
            location.casefold() in " ".join(job.locations).casefold()
            for location in expand_location_terms(plan.locations)
        )
        else 0.0
    )
    role_score = bm25 / max(1, len(query))
    job_skill_evidence = extract_skills(f"{job.title} {job.description}")
    matched_profile_skills = tuple(
        sorted(set(profile_skill_evidence) & set(job_skill_evidence))
    )
    missing_job_skills = tuple(
        sorted(set(job_skill_evidence) - set(profile_skill_evidence))
    )
    required_job_skills = extract_required_skills(job.description)
    missing_required_skills = tuple(
        sorted(set(required_job_skills) - set(profile_skill_evidence))
    )
    skill_score = (
        len(matched_profile_skills) / len(job_skill_evidence)
        if profile_skill_evidence and job_skill_evidence
        else 0.0
    )
    score = min(
        1.0,
        role_score * 0.55 + skill_score * 0.35 + title_bonus + location_bonus,
    )
    warnings = []
    if job.source.liveness == JobLiveness.UNKNOWN:
        warnings.append("来源刷新失败或岗位缺少有效性验证")
    if job.salary is None and job.salary_min_k is None:
        warnings.append("岗位未公开薪资")
    if profile_skill_evidence and missing_job_skills:
        warnings.append(f"简历未提供这些技能证据：{', '.join(missing_job_skills)}")
    if profile_skill_evidence and missing_required_skills:
        warnings.append(f"岗位必备技能缺口：{', '.join(missing_required_skills)}")
    if (
        profile_experience is not None
        and job.experience_min_years is not None
        and profile_experience < job.experience_min_years
    ):
        warnings.append(
            f"岗位要求至少{job.experience_min_years}年，"
            f"简历可确认约{profile_experience}年"
        )
    if title_bonus:
        reasons = [f"岗位名称与目标方向“{plan.target_roles[0]}”直接匹配"]
    elif matched:
        reasons = ["岗位职责与目标方向存在关键词重合"]
    else:
        reasons = []
    if location_bonus:
        reasons.append("工作地点符合搜索计划")
    if matched_profile_skills:
        reasons.append(f"简历技能覆盖：{', '.join(matched_profile_skills)}")
    evidence_pairs = tuple(
        EvidencePair(
            criterion=skill,
            profile_evidence=profile_skill_evidence[skill],
            job_evidence=job_skill_evidence[skill],
        )
        for skill in matched_profile_skills
    )
    return JobMatch(
        job=job,
        score=round(score, 6),
        evidence=MatchEvidence(
            hard_filter_passed=True,
            matched_terms=tuple(matched),
            reasons=tuple(reasons),
            warnings=tuple(warnings),
            evidence_pairs=evidence_pairs,
            matched_profile_skills=matched_profile_skills,
            missing_job_skills=missing_job_skills,
            missing_required_skills=missing_required_skills,
        ),
    )


def _profile_experience_years(profile: ProfileSummary | None) -> int | None:
    if profile is None:
        return None
    values = [
        int(match.group(1))
        for fact in profile.facts
        if fact.fact_type is FactType.EXPERIENCE
        for match in [re.search(r"(\d+)\s*年", fact.value)]
        if match
    ]
    return max(values, default=None)


def _annual_salary_min(job: JobPosting) -> int | None:
    if job.salary and job.salary.currency in {None, "CNY"}:
        return job.salary.normalized_annual_min
    if job.salary_min_k is not None:
        return job.salary_min_k * 1000 * 12
    return None


def _annual_salary_max(job: JobPosting) -> int | None:
    if job.salary and job.salary.currency in {None, "CNY"}:
        return job.salary.normalized_annual_max
    if job.salary_max_k is not None:
        return job.salary_max_k * 1000 * 12
    return None
