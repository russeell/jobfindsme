from __future__ import annotations

from datetime import UTC, datetime

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    EmploymentType,
    RecruitmentTrack,
    SearchPlan,
    SourceKind,
)
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.matching import DeterministicMatcher
from jobfindsme.matching.tokenizer import tokenize
from jobfindsme.profiles.models import FactStatus, FactType, ProfileFact, ProfileSummary

NOW = datetime(2026, 7, 28, tzinfo=UTC)


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


def test_unknown_salary_is_retained_with_warning() -> None:
    match = DeterministicMatcher().match(
        plan(),
        [job("unknown", description="Python RAG Agent，1-3年")],
    )[0]

    assert "岗位未公开薪资" in match.evidence.warnings


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
        plan(),
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
