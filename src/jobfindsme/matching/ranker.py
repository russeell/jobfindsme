from __future__ import annotations

import math
from collections import Counter

from jobfindsme.contracts import (
    JobLiveness,
    JobMatch,
    JobPosting,
    MatchEvidence,
    SearchPlan,
)
from jobfindsme.matching.tokenizer import tokenize


class DeterministicMatcher:
    """Apply hard constraints first, then rank with explainable BM25-style terms."""

    def match(
        self,
        plan: SearchPlan,
        jobs: list[JobPosting],
        *,
        limit: int = 20,
    ) -> list[JobMatch]:
        eligible = [job for job in jobs if self._hard_filter(plan, job)]
        if not eligible:
            return []
        query_terms = tokenize(" ".join(plan.target_roles))
        documents = [tokenize(f"{job.title} {job.description}") for job in eligible]
        document_frequency = Counter(
            term for document in documents for term in set(document)
        )
        matches = [
            self._score(
                plan,
                job,
                terms,
                query_terms,
                document_frequency,
                len(eligible),
            )
            for job, terms in zip(eligible, documents, strict=True)
        ]
        return sorted(matches, key=lambda item: (-item.score, item.job.job_id))[:limit]

    @staticmethod
    def _hard_filter(plan: SearchPlan, job: JobPosting) -> bool:
        if job.source.liveness in {JobLiveness.CLOSED, JobLiveness.STALE}:
            return False
        searchable = (
            f"{job.title} {job.description} {' '.join(job.locations)}".casefold()
        )
        if any(term.casefold() in searchable for term in plan.exclusions):
            return False
        if plan.locations and not any(
            location.casefold() in searchable for location in plan.locations
        ):
            return False
        if (
            plan.salary_min_k is not None
            and job.salary_max_k is not None
            and job.salary_max_k < plan.salary_min_k
        ):
            return False
        if (
            plan.salary_max_k is not None
            and job.salary_min_k is not None
            and job.salary_min_k > plan.salary_max_k
        ):
            return False
        return not (
            plan.experience_max_years is not None
            and job.experience_min_years is not None
            and job.experience_min_years > plan.experience_max_years
        )

    @staticmethod
    def _score(
        plan: SearchPlan,
        job: JobPosting,
        document: tuple[str, ...],
        query: tuple[str, ...],
        document_frequency: Counter[str],
        document_count: int,
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
            if any(
                role.casefold() in job.title.casefold() for role in plan.target_roles
            )
            else 0.0
        )
        location_bonus = (
            0.1
            if plan.locations
            and any(
                location.casefold() in " ".join(job.locations).casefold()
                for location in plan.locations
            )
            else 0.0
        )
        score = min(1.0, bm25 / max(1, len(query)) + title_bonus + location_bonus)
        warnings = []
        if job.source.liveness == JobLiveness.UNKNOWN:
            warnings.append("岗位缺少可验证的发布日期")
        if job.salary_min_k is None:
            warnings.append("岗位未公开薪资")
        reasons = [f"匹配关键词：{', '.join(matched)}"] if matched else []
        if title_bonus:
            reasons.append("职位名称直接匹配目标岗位")
        if location_bonus:
            reasons.append("工作地点符合搜索计划")
        return JobMatch(
            job=job,
            score=round(score, 6),
            evidence=MatchEvidence(
                hard_filter_passed=True,
                matched_terms=tuple(matched),
                reasons=tuple(reasons),
                warnings=tuple(warnings),
            ),
        )
