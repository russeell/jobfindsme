from __future__ import annotations

from datetime import UTC, datetime

from evaluation.regression.legacy_matcher import LegacyBM25Matcher
from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    EmploymentType,
    RecruitmentTrack,
    SalaryPolicy,
    SearchPlan,
    SourceKind,
)
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.matching import (
    filter_jobs,
    score_signals,
    tokenize,
    undisclosed_salary_counts,
)
from jobfindsme.profiles.models import FactStatus, FactType, ProfileFact, ProfileSummary

NOW = datetime(2026, 7, 28, tzinfo=UTC)

DeterministicMatcher = LegacyBM25Matcher


def plan(**overrides: object) -> SearchPlan:
    values: dict[str, object] = {
        "plan_id": "plan-1",
        "workspace_id": "workspace-1",
        "name": "AI 求职",
        "target_roles": ("AI应用工程师",),
        "locations": ("杭州",),
        "salary_min_k": 20,
        "experience_max_years": 3,
        "exclusions": ("外包", "驻场"),
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return SearchPlan(**values)


def job(
    external_id: str,
    *,
    title: str = "AI应用工程师",
    description: str = "Python RAG Agent，1-3年，25-40K",
    location: str = "杭州",
    published_at: str = "2026-07-27T00:00:00Z",
):
    raw = RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name="企业官网",
        source_url=f"https://careers.example.com/{external_id}",
        external_id=external_id,
        payload={
            "title": title,
            "company": "示例科技",
            "description": description,
            "location": location,
            "url": f"https://careers.example.com/{external_id}",
            "published_at": published_at,
        },
    )
    return normalize_job(raw, fetched_at=NOW)


def test_matcher_applies_constraints_before_ranking() -> None:
    jobs = [
        job("best"),
        job("wrong-city", location="北京"),
        job("outsourcing", description="AI应用工程师，外包驻场，25-40K"),
        job("senior", description="AI应用工程师，5-8年，30-50K"),
        job("stale", published_at="2025-01-01T00:00:00Z"),
    ]

    matches = DeterministicMatcher().match(plan(), jobs)

    assert [match.job.external_id for match in matches] == ["best"]
    assert matches[0].evidence.hard_filter_passed is True
    assert "工作地点符合搜索计划" in matches[0].evidence.reasons
    assert matches[0].job.source.source_url


def test_chinese_city_filter_matches_english_china_source_location() -> None:
    jobs = [
        job("shanghai", location="CN - Shanghai"),
        job("beijing", location="CN - Beijing"),
    ]

    matches = DeterministicMatcher().match(
        plan(locations=("上海",), salary_min_k=None),
        jobs,
    )

    assert [match.job.external_id for match in matches] == ["shanghai"]
    assert "工作地点符合搜索计划" in matches[0].evidence.reasons


def test_location_only_non_technical_job_never_enters_candidates() -> None:
    jobs = [
        job("account", title="Account Manager", location="上海"),
        job("ai", title="AI应用工程师", location="上海"),
    ]

    matches = DeterministicMatcher().match(
        plan(locations=("上海",), salary_min_k=None),
        jobs,
    )

    assert [match.job.external_id for match in matches] == ["ai"]


def test_ai_keywords_do_not_make_product_manager_an_engineering_candidate() -> None:
    matches = DeterministicMatcher().match(
        plan(locations=("上海",), salary_min_k=None),
        [
            job(
                "product-manager",
                title="AI Agent /大模型/搜索/推荐算法产品经理",
                location="上海",
            ),
            job(
                "engineer",
                title="AI Agent 后端工程师（RAG方向）",
                location="上海",
            ),
        ],
    )

    assert [match.job.external_id for match in matches] == ["engineer"]


def test_product_manager_remains_valid_when_explicitly_requested() -> None:
    matches = DeterministicMatcher().match(
        plan(
            target_roles=("AI产品经理",),
            locations=("上海",),
            salary_min_k=None,
        ),
        [
            job(
                "product-manager",
                title="AI Agent 产品经理",
                location="上海",
            )
        ],
    )

    assert [match.job.external_id for match in matches] == ["product-manager"]


def test_entry_level_plan_rejects_senior_title_without_structured_years() -> None:
    matches = DeterministicMatcher().match(
        plan(experience_max_years=3, salary_min_k=None),
        [
            job("senior", title="资深 AI 研发效能架构师"),
            job("regular", title="AI Agent应用工程师"),
        ],
    )

    assert [match.job.external_id for match in matches] == ["regular"]


def test_exact_title_ranks_above_partial_description_match() -> None:
    jobs = [
        job("exact"),
        job(
            "partial",
            title="Python后端工程师",
            description="参与AI应用工程师相关的RAG平台开发，1-3年，25-40K",
        ),
    ]

    matches = DeterministicMatcher().match(plan(), jobs)

    assert [match.job.external_id for match in matches] == ["exact", "partial"]
    assert matches[0].score > matches[1].score


def test_unknown_salary_is_excluded_when_salary_is_a_hard_constraint() -> None:
    matches = DeterministicMatcher().match(
        plan(),
        [job("unknown", description="Python RAG Agent，1-3年")],
    )

    assert matches == []


def test_unknown_salary_can_be_kept_only_with_explicit_policy() -> None:
    unknown = job("unknown", description="Python RAG Agent，1-3年")

    passed = filter_jobs(
        plan(salary_policy=SalaryPolicy.INCLUDE_UNDISCLOSED),
        [unknown],
    )

    assert [item.external_id for item in passed] == ["unknown"]


def test_unknown_salary_policy_produces_explicit_diagnostics() -> None:
    unknown = job("unknown", description="Python RAG Agent，1-3年")

    assert undisclosed_salary_counts(plan(), [unknown]) == (1, 0)
    assert undisclosed_salary_counts(
        plan(salary_policy=SalaryPolicy.INCLUDE_UNDISCLOSED), [unknown]
    ) == (0, 1)


def test_minimum_salary_requires_the_posted_lower_bound_to_match() -> None:
    matches = DeterministicMatcher().match(
        plan(salary_min_k=20),
        [
            job("below", description="Python RAG Agent，1-3年，18-30K"),
            job("meets", description="Python RAG Agent，1-3年，20-30K"),
        ],
    )

    assert [match.job.external_id for match in matches] == ["meets"]
    assert "岗位未公开薪资" not in matches[0].evidence.warnings


def test_strict_track_and_type_do_not_accept_unknown_classification() -> None:
    strict_plan = plan(
        recruitment_track=RecruitmentTrack.SOCIAL,
        employment_type=EmploymentType.FULL_TIME,
    )
    matches = DeterministicMatcher().match(
        strict_plan,
        [
            job("unknown", description="Python RAG Agent，1-3年，25-40K"),
            job(
                "social-full-time",
                description="社会招聘，全职正式岗位，Python RAG Agent，1-3年，25-40K",
            ),
        ],
    )

    assert [match.job.external_id for match in matches] == ["social-full-time"]


def test_confirmed_profile_skills_change_ranking_and_keep_evidence() -> None:
    profile = ProfileSummary(
        profile_id="profile-1",
        workspace_id="workspace-1",
        facts=(
            ProfileFact(
                fact_id="fact-1",
                fact_type=FactType.SKILL,
                value="Python",
                evidence_snippet="使用 Python 构建 RAG 服务",
                evidence_start=0,
                evidence_end=6,
                status=FactStatus.CONFIRMED,
            ),
            ProfileFact(
                fact_id="fact-2",
                fact_type=FactType.SKILL,
                value="RAG",
                evidence_snippet="负责 RAG 检索链路",
                evidence_start=7,
                evidence_end=10,
                status=FactStatus.CONFIRMED,
            ),
        ),
    )
    jobs = [
        job("java", description="Java Spring 云原生平台，1-3年，25-40K"),
        job("python", description="Python RAG Agent，1-3年，25-40K"),
    ]

    matches = DeterministicMatcher().match(plan(), jobs, profile=profile)

    assert [item.job.external_id for item in matches] == ["python", "java"]
    assert matches[0].evidence.matched_profile_skills == ("Python", "RAG")
    assert {pair.criterion for pair in matches[0].evidence.evidence_pairs} == {
        "Python",
        "RAG",
    }
    assert "Java" in matches[1].evidence.missing_job_skills


def test_chinese_tokenizer_keeps_words_and_ngrams() -> None:
    tokens = tokenize("大模型应用工程师")

    assert "大模型应用工程师" in tokens
    assert "应用工程师" not in tokens
    assert "应用" in tokens
    assert "工程师" in tokens


def test_required_skill_gap_is_explicit() -> None:
    profile = ProfileSummary(
        profile_id="profile-1",
        workspace_id="workspace-1",
        facts=(
            ProfileFact(
                fact_id="fact-1",
                fact_type=FactType.SKILL,
                value="Python",
                evidence_snippet="Python",
                evidence_start=0,
                evidence_end=6,
                status=FactStatus.CONFIRMED,
            ),
        ),
    )

    match = DeterministicMatcher().match(
        plan(salary_min_k=None),
        [
            job(
                "required",
                description="任职要求：熟悉 Python，必须掌握 Kubernetes",
            )
        ],
        profile=profile,
    )[0]

    assert match.evidence.missing_required_skills == ("Kubernetes",)
    assert any("必备技能缺口" in item for item in match.evidence.warnings)


# ── v0.4.1: signal coarse ranking (filter_jobs / score_signals) ───────────────


def _profile(*skills: str, experience: str = "", degree: str = "") -> ProfileSummary:
    facts: list[ProfileFact] = []
    for index, skill in enumerate(skills):
        facts.append(
            ProfileFact(
                fact_id=f"skill-{index}",
                fact_type=FactType.SKILL,
                value=skill,
                evidence_snippet=skill,
                evidence_start=0,
                evidence_end=len(skill),
                status=FactStatus.CONFIRMED,
            )
        )
    if experience:
        facts.append(
            ProfileFact(
                fact_id="exp",
                fact_type=FactType.EXPERIENCE,
                value=experience,
                evidence_snippet=experience,
                evidence_start=0,
                evidence_end=len(experience),
                status=FactStatus.CONFIRMED,
            )
        )
    if degree:
        facts.append(
            ProfileFact(
                fact_id="edu",
                fact_type=FactType.EDUCATION,
                value=degree,
                evidence_snippet=degree,
                evidence_start=0,
                evidence_end=len(degree),
                status=FactStatus.CONFIRMED,
            )
        )
    return ProfileSummary(
        profile_id="profile-1",
        workspace_id="workspace-1",
        facts=tuple(facts),
    )


def test_filter_jobs_returns_all_when_pool_within_limit() -> None:
    jobs = [job("a"), job("b"), job("c")]

    passed = filter_jobs(plan(), jobs, profile=_profile("Python"), limit=20)

    assert [item.external_id for item in passed] == ["a", "b", "c"]


def test_filter_jobs_sorts_by_score_even_when_pool_within_limit() -> None:
    jobs = [
        job("low", description="Java Spring 云原生平台，1-3年，25-40K"),
        job("high", description="Python RAG Agent，1-3年，25-40K"),
    ]

    passed = filter_jobs(plan(), jobs, profile=_profile("Python", "RAG"), limit=20)

    assert [item.external_id for item in passed] == ["high", "low"]


def test_filter_jobs_truncates_to_limit_with_profile() -> None:
    jobs = [job(f"job-{index}") for index in range(30)]

    passed = filter_jobs(plan(), jobs, profile=_profile("Python"), limit=20)

    assert len(passed) == 20


def test_filter_jobs_orders_highest_signal_score_first() -> None:
    jobs = [
        job("java", description="Java Spring 云原生平台，1-3年，25-40K"),
        job("python", description="Python RAG Agent，1-3年，25-40K"),
        job("both", description="Python RAG Java 微服务，1-3年，25-40K"),
    ]

    passed = filter_jobs(plan(), jobs, profile=_profile("Python", "RAG"), limit=2)

    assert [item.external_id for item in passed] == ["python", "both"]


def test_experience_range_must_overlap_plan_range() -> None:
    jobs = [
        job("junior", description="AI应用工程师，1-3年，25-40K"),
        job("matching", description="AI应用工程师，5-8年，25-40K"),
        job("unknown", description="AI应用工程师，经验不限，25-40K"),
    ]

    passed = filter_jobs(
        plan(experience_min_years=5, experience_max_years=10),
        jobs,
        limit=20,
    )

    assert [item.external_id for item in passed] == ["matching", "unknown"]


def test_score_signals_skill_overlap_dominates() -> None:
    python_job = job("python", description="Python RAG Agent，1-3年，25-40K")
    java_job = job("java", description="Java Spring 云原生平台，1-3年，25-40K")

    python_score = score_signals(python_job, _profile("Python", "RAG"))
    java_score = score_signals(java_job, _profile("Python", "RAG"))

    assert python_score > java_score
    assert 0.0 < python_score <= 1.0


def test_score_signals_experience_alignment() -> None:
    senior_job = job("senior", description="AI应用工程师，5-8年，25-40K")
    junior_job = job("junior", description="AI应用工程师，1-3年，25-40K")
    profile = _profile("Python", experience="3年")

    senior_score = score_signals(senior_job, profile)
    junior_score = score_signals(junior_job, profile)

    assert junior_score > senior_score  # 经验满足 > 经验略低


def test_score_signals_degree_match() -> None:
    master_profile = _profile("Python", degree="上海大学 计算机科学 硕士")
    bachelor_profile = _profile("Python", degree="上海大学 计算机科学 本科")
    phd_required = job("phd", description="AI应用工程师，博士学历，1-3年，25-40K")

    assert (
        score_signals(phd_required, master_profile)
        < score_signals(phd_required, bachelor_profile) + 0.5
    )  # 两者都在低分区，只验证不报错且有序可比较


def test_score_signals_returns_zero_without_profile() -> None:
    assert score_signals(job("plain"), None) == 0.0


# ── Regression: salary conflict — raw vs structured ────────────────────


def test_raw_text_lower_than_structured_min_is_filtered_by_strict_salary() -> None:
    """When raw salary text shows 18K but structured fields claim 20K,
    the strict salary_min_k=20 filter must use the conservative (lower)
    value and exclude the job."""
    from jobfindsme.contracts import SalaryDetails, SalaryPeriod
    from jobfindsme.importing.normalizer import _reconcile_salary

    # Simulate: structured says 20K, raw_text says "18-30K"
    details = SalaryDetails(
        raw_text="18-30K",
        currency="CNY",
        period=SalaryPeriod.MONTH,
        min_amount=20000,
        max_amount=30000,
        months_per_year=12,
        normalized_annual_min=20000 * 12,
        normalized_annual_max=30000 * 12,
    )
    new_min, new_max, new_details = _reconcile_salary(20, 30, details)

    # Must use the conservative raw-text value (18K monthly)
    assert new_min == 18
    assert new_details is not None
    # normalized_annual_min should now reflect 18K, not 20K
    assert new_details.normalized_annual_min == 18 * 1000 * 12  # 216000
    assert new_details.normalized_annual_min < 20 * 1000 * 12  # < 240000


def test_raw_text_consistent_with_structured_is_not_adjusted() -> None:
    """When raw text and structured fields agree, no adjustment needed."""
    from jobfindsme.contracts import SalaryDetails, SalaryPeriod
    from jobfindsme.importing.normalizer import _reconcile_salary

    details = SalaryDetails(
        raw_text="25-40K",
        currency="CNY",
        period=SalaryPeriod.MONTH,
        min_amount=25000,
        max_amount=40000,
        months_per_year=12,
        normalized_annual_min=25000 * 12,
        normalized_annual_max=40000 * 12,
    )
    new_min, new_max, new_details = _reconcile_salary(25, 40, details)

    assert new_min == 25  # Unchanged
    assert new_max == 40  # Unchanged
    assert new_details is details  # Same object returned


def test_parse_monthly_salary_min_k_returns_monthly_base() -> None:
    """parse_monthly_salary_min_k returns monthly K, not annualised."""
    from jobfindsme.importing.normalizer import parse_monthly_salary_min_k

    # Plain monthly: returns the base K value
    assert parse_monthly_salary_min_k("18-30K") == 18.0
    assert parse_monthly_salary_min_k("20-40K") == 20.0
    # With bonus months: returns monthly base, NOT bonus-inflated annual
    assert parse_monthly_salary_min_k("18-30K·15薪") == 18.0
    assert parse_monthly_salary_min_k("20-40K·15薪") == 20.0
    # Decimal
    assert parse_monthly_salary_min_k("18.5-30.5K") == 18.5
    # Yearly → conservative /12
    result = parse_monthly_salary_min_k("20-30万/年")
    assert abs(result - 20 * 10 / 12) < 0.01  # ≈ 16.67
    # Non-salary text
    assert parse_monthly_salary_min_k("面议") is None
    assert parse_monthly_salary_min_k("") is None


def test_18_30K_15salary_filtered_by_strict_20k() -> None:
    """18-30K·15薪 has a monthly base of 18K — must be filtered when
    salary_min_k=20 with STRICT policy.

    The bonus months (·15薪) increase the ANNUAL total but the plan
    threshold is in monthly-K terms; 18K < 20K so the job is excluded.
    """
    raw = RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name="企业官网",
        source_url="https://careers.example.com/job-18k",
        external_id="job-18k",
        payload={
            "title": "AI应用工程师",
            "company": "示例科技",
            "description": "Python RAG Agent 大模型 18-30K·15薪",
            "location": "杭州",
            "url": "https://careers.example.com/job-18k",
            "published_at": "2026-07-27T00:00:00Z",
        },
    )
    j = normalize_job(raw, fetched_at=NOW)

    # Verify the job has monthly min 18K in raw text
    from jobfindsme.importing.normalizer import parse_monthly_salary_min_k

    raw_monthly = parse_monthly_salary_min_k("18-30K·15薪")
    assert raw_monthly == 18.0

    # Strict filter with salary_min_k=20 must exclude it
    p = plan(salary_min_k=20, salary_policy=SalaryPolicy.STRICT)
    result = filter_jobs(p, [j], limit=20)
    assert len(result) == 0, (
        f"18K monthly job should be filtered by strict 20K threshold, "
        f"but {len(result)} passed"
    )

    # Same job with salary_min_k=15 should pass
    p15 = plan(salary_min_k=15, salary_policy=SalaryPolicy.STRICT)
    result15 = filter_jobs(p15, [j], limit=20)
    assert len(result15) == 1


def test_monthly_salary_min_k_uses_lowest_candidate_across_sources() -> None:
    """_monthly_salary_min_k returns min(salary_min_k, raw_text, salary details)."""
    from jobfindsme.contracts import SalaryDetails, SalaryPeriod
    from jobfindsme.matching import _monthly_salary_min_k

    j = job(
        "conflict",
        description="AI应用工程师 20-30K",
    )
    j = j.model_copy(
        update={
            "salary_min_k": 20,
            "salary": SalaryDetails(
                raw_text="18-30K",
                currency="CNY",
                period=SalaryPeriod.MONTH,
                min_amount=18000,
                max_amount=30000,
                months_per_year=12,
                normalized_annual_min=18000 * 12,
                normalized_annual_max=30000 * 12,
            ),
        }
    )
    monthly = _monthly_salary_min_k(j)
    assert monthly == 18  # conservative — raw text 18K beats structured 20K


def test_monthly_salary_min_k_returns_none_for_day_hour_unknown() -> None:
    """DAY / HOUR / UNKNOWN periods must not pretend to be monthly."""
    from jobfindsme.contracts import SalaryDetails, SalaryPeriod
    from jobfindsme.matching import _monthly_salary_min_k

    day_job = job("day-rate", description="AI工程师 500-800/天").model_copy(
        update={
            "salary": SalaryDetails(
                raw_text="500-800/天",
                currency="CNY",
                period=SalaryPeriod.DAY,
                min_amount=500,
                max_amount=800,
            ),
        }
    )
    assert _monthly_salary_min_k(day_job) is None


# ── _reconcile_salary edge cases ────────────────────────────────────────


def test_reconcile_salary_handles_decimal_values() -> None:
    """Decimal monthly salaries are parsed correctly."""
    from jobfindsme.contracts import SalaryDetails, SalaryPeriod
    from jobfindsme.importing.normalizer import _reconcile_salary

    details = SalaryDetails(
        raw_text="18.5-30.5K",
        currency="CNY",
        period=SalaryPeriod.MONTH,
        min_amount=18500,
        max_amount=30500,
        months_per_year=12,
        normalized_annual_min=18500 * 12,
        normalized_annual_max=30500 * 12,
    )
    # No conflict — structured and raw agree
    new_min, new_max, new_details = _reconcile_salary(19, 31, details)
    # 18.5 < 19 so should adjust
    assert new_min == 18
    assert new_max == 30


def test_reconcile_salary_skips_yearly_raw_text() -> None:
    """Yearly raw text like "20-30万/年" does not match the monthly regex,
    so _reconcile_salary returns early without adjustment."""
    from jobfindsme.contracts import SalaryDetails, SalaryPeriod
    from jobfindsme.importing.normalizer import _reconcile_salary

    details = SalaryDetails(
        raw_text="20-30万/年",
        currency="CNY",
        period=SalaryPeriod.YEAR,
        min_amount=200000,
        max_amount=300000,
        normalized_annual_min=200000,
        normalized_annual_max=300000,
    )
    new_min, new_max, new_details = _reconcile_salary(25, 35, details)
    # yearly raw text is in different units — must not be compared with monthly K
    assert new_min == 25  # unchanged
    assert new_details is details


def test_reconcile_salary_skips_mianyi() -> None:
    """面议 raw_text has no parseable number — return early."""
    from jobfindsme.contracts import SalaryDetails
    from jobfindsme.importing.normalizer import _reconcile_salary

    details = SalaryDetails(raw_text="面议")
    new_min, _, new_details = _reconcile_salary(25, 35, details)
    assert new_min == 25  # unchanged
    assert new_details is details


def test_reconcile_salary_skips_empty_raw_text() -> None:
    """Empty or None raw_text should not trigger reconciliation."""
    from jobfindsme.importing.normalizer import _reconcile_salary

    new_min, _, _ = _reconcile_salary(25, 35, None)
    assert new_min == 25  # unchanged
