from __future__ import annotations

from datetime import UTC, datetime

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import SearchPlan, SourceKind
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.matching import DeterministicMatcher

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
