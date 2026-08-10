"""Legacy BM25 matcher kept only for historical evaluation replay."""

from __future__ import annotations

import math
from collections import Counter

from jobfindsme.contracts import (
    EvidencePair,
    JobLiveness,
    JobMatch,
    JobPosting,
    MatchEvidence,
    SearchPlan,
)
from jobfindsme.matching.ranker import _hard_filter, _profile_experience_years
from jobfindsme.matching.tokenizer import tokenize
from jobfindsme.profiles.models import FactType, ProfileSummary
from jobfindsme.taxonomy import (
    expand_location_terms,
    expand_role_terms,
    extract_required_skills,
    extract_skills,
)


class LegacyBM25Matcher:
    """Frozen pre-v0.4 matcher for regression fixtures, never production search."""

    stale_after_days: int | None = None

    def match(
        self,
        plan: SearchPlan,
        jobs: list[JobPosting],
        *,
        profile: ProfileSummary | None = None,
        limit: int = 20,
        min_score: float = 0.10,
        stale_after_days: int | None = None,
    ) -> list[JobMatch]:
        effective_stale = (
            self.stale_after_days if stale_after_days is None else stale_after_days
        )
        eligible = [
            job
            for job in jobs
            if _hard_filter(plan, job, stale_after_days=effective_stale)
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
        scored = [match for match in matches if match.score >= min_score]
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
