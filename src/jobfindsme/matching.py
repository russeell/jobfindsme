"""Job filtering and signal-based coarse ranking.

Since v0.4 the matcher no longer produces BM25 scores.  The pipeline is:

1. Hard filter — remove jobs that violate objective constraints
2. Signal extraction — pull skills, experience, degree from each JD
3. Coarse rank (v0.4.1) — deterministic signal-match score, Top-20 cut
4. Server presentation — stable, evidence-backed ordering across Agent hosts
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from jobfindsme.contracts import (
    EmploymentType,
    JobLiveness,
    JobPosting,
    RecruitmentTrack,
    SalaryPolicy,
    SearchPlan,
)
from jobfindsme.importing.normalizer import parse_monthly_salary_min_k
from jobfindsme.profiles.models import FactType, ProfileSummary
from jobfindsme.taxonomy import (
    expand_location_terms,
    extract_skills,
    is_target_role_candidate,
)

# ── Degree ordering for comparison ──────────────────────────────────────────

_DEGREE_ORDER = {"大专": 1, "本科": 2, "硕士": 3, "博士": 4, "不限": 0}


# ── Public API ────────────────────────────────────────────────────────────────


def filter_jobs(
    plan: SearchPlan,
    jobs: list[JobPosting],
    *,
    profile: ProfileSummary | None = None,
    limit: int = 20,
    stale_after_days: int | None = 7,
) -> list[JobPosting]:
    """Return hard-filter-passing jobs, coarse-ranked by signal match.

    If *profile* is provided, jobs are scored against profile facts
    (skills, experience, degree) and sorted descending — even when the
    eligible pool fits within *limit*, so the presented list always starts
    with the strongest matches.  The top *limit* are returned.  Sorting is
    stable, so ties keep their natural order.

    Without a profile there is no score, so jobs pass through in natural
    order.
    """
    eligible = [
        job
        for job in jobs
        if _hard_filter(plan, job, stale_after_days=stale_after_days)
    ]
    if profile is None:
        return eligible[:limit]

    # Coarse ranking: deterministic signal-match score
    scored = [(job, _score_signals(job, profile)) for job in eligible]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [job for job, _ in scored[:limit]]


def eligible_count(
    plan: SearchPlan,
    jobs: list[JobPosting],
    *,
    stale_after_days: int | None = 7,
) -> int:
    """Count jobs that pass the production hard-filter contract."""
    return sum(
        1 for job in jobs if _hard_filter(plan, job, stale_after_days=stale_after_days)
    )


def has_undisclosed_salary(job: JobPosting) -> bool:
    """Return true when no comparable CNY monthly lower bound is available."""
    return _monthly_salary_min_k(job) is None


def undisclosed_salary_counts(
    plan: SearchPlan,
    jobs: list[JobPosting],
    *,
    stale_after_days: int | None = 7,
) -> tuple[int, int]:
    """Return (filtered, included) unknown-salary counts for diagnostics.

    Only jobs that satisfy every non-salary hard constraint are counted.
    """
    if plan.salary_min_k is None and plan.salary_max_k is None:
        return 0, 0
    permissive = plan.model_copy(
        update={"salary_policy": SalaryPolicy.INCLUDE_UNDISCLOSED}
    )
    eligible_unknown = sum(
        1
        for job in jobs
        if has_undisclosed_salary(job)
        and _hard_filter(permissive, job, stale_after_days=stale_after_days)
    )
    if plan.salary_policy is SalaryPolicy.STRICT:
        return eligible_unknown, 0
    return 0, eligible_unknown


def extract_job_signals(job: JobPosting) -> dict:
    """Extract structured signals for deterministic ranking and explanation.

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


# ── Signal-match scoring (v0.4.1) ────────────────────────────────────────────


def score_signals(
    job: JobPosting,
    profile: ProfileSummary | None,
) -> float:
    """Deterministic match score, 0.0 or 0.60–1.0.

    A job that reaches this function has already passed every decidable
    hard constraint (role, location, salary, track, type, experience), so
    the score starts at 0.60 and adds up to 0.40 from evidence signals
    (skill overlap dominates, then experience, degree, liveness, salary).
    This keeps every recommendable job in the 60%–100% band instead of
    punishing candidates whose JD text is sparse. The server owns this
    reproducible ordering; a host Agent may explain it but must not
    silently replace it.

    Returns 0.0 when *profile* is None (no scoring without a profile).
    """
    if profile is None:
        return 0.0
    return _score_signals(job, profile)


def _score_signals(
    job: JobPosting,
    profile: ProfileSummary,
) -> float:
    """Deterministic signal score: 0.60 hard-condition floor + 0.40 bonus."""
    signals = extract_job_signals(job)

    profile_skills = {
        fact.value.casefold()
        for fact in profile.facts
        if fact.fact_type is FactType.SKILL
    }
    profile_degree = _profile_highest_degree(profile)
    profile_exp_years = _profile_experience_years(profile)

    score = 0.0
    details: list[str] = []

    # ── Skill overlap (up to 0.50) ──
    if signals["required_skills"] and profile_skills:
        jd_set = {s.casefold() for s in signals["required_skills"]}
        overlap = jd_set & profile_skills
        if jd_set:
            skill_ratio = len(overlap) / len(jd_set)
            skill_score = min(0.50, skill_ratio * 0.50)
            score += skill_score
            if overlap:
                details.append(f"技能命中{len(overlap)}/{len(jd_set)}")

    # ── Experience alignment (up to 0.25) ──
    if profile_exp_years is not None and job.experience_min_years is not None:
        if profile_exp_years >= job.experience_min_years:
            score += 0.25
            details.append("经验满足")
        elif profile_exp_years >= job.experience_min_years - 2:
            score += 0.10
            details.append(
                f"经验略低(要求{job.experience_min_years}年,简历{profile_exp_years}年)"
            )
    elif profile_exp_years is not None:
        score += 0.12  # unknown requirement → partial credit
        details.append("经验要求未标注")

    # ── Degree match (up to 0.10) ──
    jd_degree = signals["required_degree"]
    if jd_degree and profile_degree:
        jd_level = _DEGREE_ORDER.get(jd_degree, 0)
        pf_level = _DEGREE_ORDER.get(profile_degree, 0)
        if pf_level >= jd_level and jd_level > 0:
            score += 0.10
            details.append(f"学历匹配({profile_degree}≥{jd_degree})")
        elif pf_level > 0:
            score += 0.03
            details.append(f"学历略低(要求{jd_degree},简历{profile_degree})")

    # ── Liveness bonus (up to 0.05) ──
    if job.source.liveness is JobLiveness.ACTIVE:
        score += 0.05
    elif job.source.liveness is JobLiveness.UNKNOWN:
        score += 0.01

    # ── Salary presence (up to 0.05) ──
    if job.salary_min_k or (job.salary and job.salary.raw_text):
        score += 0.05

    normalized = score / 0.95  # signal part never exceeds 0.95
    return round(min(1.0, 0.60 + 0.40 * normalized), 4)


def _profile_highest_degree(profile: ProfileSummary) -> str | None:
    """Walk profile facts for the highest education level."""
    best = ""
    best_order = 0
    for fact in profile.facts:
        if fact.fact_type is FactType.EDUCATION:
            for label, order in _DEGREE_ORDER.items():
                if label in fact.value and order > best_order:
                    best = label
                    best_order = order
    return best or None


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
    monthly_min = _monthly_salary_min_k(job)
    if plan.salary_min_k is not None:
        if monthly_min is None and plan.salary_policy is SalaryPolicy.STRICT:
            return False
        if monthly_min is not None and monthly_min < plan.salary_min_k:
            return False
    if plan.salary_max_k is not None:
        if monthly_min is None and plan.salary_policy is SalaryPolicy.STRICT:
            return False
        if monthly_min is not None and monthly_min > plan.salary_max_k:
            return False
    if (
        plan.experience_min_years is not None
        and job.experience_max_years is not None
        and job.experience_max_years < plan.experience_min_years
    ):
        return False
    return not (
        plan.experience_max_years is not None
        and job.experience_min_years is not None
        and job.experience_min_years > plan.experience_max_years
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


def _monthly_salary_min_k(job: JobPosting) -> int | None:
    """Conservative monthly minimum salary in K (月薪K下限).

    Uses the most conservative available source so the strict filter
    never passes a job whose visible monthly salary is below threshold.
    The canonical source is ``job.salary`` (Salary.monthly_min_k); the
    legacy ``salary_min_k`` mirror and raw-text parsing are conservative
    cross-checks only.
    """
    candidates: list[int] = []

    if job.salary:
        derived = job.salary.monthly_min_k
        if derived is not None:
            candidates.append(derived)

    # Parse raw_text for monthly K via the shared function
    if job.salary and job.salary.raw_text:
        monthly = parse_monthly_salary_min_k(job.salary.raw_text)
        if monthly is not None:
            candidates.append(int(monthly))

    # Legacy mirror cross-check (always derived from salary during import).
    if job.salary_min_k is not None:
        candidates.append(job.salary_min_k)

    if not candidates:
        return None
    return min(candidates)


def _monthly_salary_max_k(job: JobPosting) -> int | None:
    """Conservative monthly maximum salary in K (月薪K上限)."""
    candidates: list[int] = []
    if job.salary:
        derived = job.salary.monthly_max_k
        if derived is not None:
            candidates.append(derived)
    if job.salary_max_k is not None:
        candidates.append(job.salary_max_k)
    if not candidates:
        return None
    return max(candidates)


_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text):
        normalized = token.casefold()
        tokens.append(normalized)
        if re.fullmatch(r"[\u4e00-\u9fff]+", normalized) and len(normalized) > 1:
            for size in (2, 3):
                tokens.extend(
                    normalized[index : index + size]
                    for index in range(len(normalized) - size + 1)
                )
    return tuple(tokens)
