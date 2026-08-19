from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    DiscoverySource,
    EmploymentType,
    JobDetailLevel,
    JobLiveness,
    RecruitmentTrack,
    SalaryPeriod,
    SourceEvidence,
    SourceKind,
)
from jobfindsme.importing.discovery import JobDiscoveryService
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.parsers import parse_csv, parse_json
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import ImportSummary, JobImportService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def test_discovery_passes_primary_location_to_platform_connector() -> None:
    captured: dict[str, object] = {}

    class RecordingImports:
        def import_connector(self, workspace_id, connector, **kwargs):
            captured["workspace_id"] = workspace_id
            captured["connector"] = connector
            captured["enrich_limit"] = kwargs.get("enrich_limit")
            return ImportSummary(0, 0, 0, ())

    service = JobDiscoveryService(RecordingImports())
    service._discover_one(
        workspace_id="workspace",
        source=DiscoverySource(
            kind="liepin_cdp",
            source_name="猎聘",
            query="AI应用工程师",
            location="上海",
        ),
    )

    # The pure-HTTP connector runs first (sub-second, no Chrome) and
    # receives the same query/city as the browser connectors did before.
    assert captured["workspace_id"] == "workspace"
    assert type(captured["connector"]).__name__ == "LiepinPureHttpConnector"
    assert captured["connector"].keyword == "AI应用工程师"
    assert captured["connector"].city == "上海"


def test_discovery_falls_back_through_connector_chain() -> None:
    """When the pure-HTTP tier is blocked, the CDP/DOM tiers must be tried
    in order, with the final DOM tier keeping its enrich_limit."""
    attempted: list[tuple[str, int]] = []

    class FlakyImports:
        def import_connector(self, workspace_id, connector, **kwargs):
            name = type(connector).__name__
            enrich_limit = kwargs.get("enrich_limit", 0)
            attempted.append((name, enrich_limit))
            if name != "LiepinConnector":
                raise RuntimeError("blocked")
            return ImportSummary(0, 0, 0, ())

    service = JobDiscoveryService(FlakyImports())
    service._discover_one(
        workspace_id="workspace",
        source=DiscoverySource(
            kind="liepin_cdp",
            source_name="猎聘",
            query="AI",
            location="上海",
        ),
    )

    assert attempted == [
        ("LiepinPureHttpConnector", 0),
        ("LiepinConnector", 3),
    ]


def test_discovery_raises_when_whole_chain_fails() -> None:
    class AlwaysFailImports:
        def import_connector(self, workspace_id, connector, **kwargs):
            raise RuntimeError("blocked")

    service = JobDiscoveryService(AlwaysFailImports())
    with pytest.raises(RuntimeError, match="blocked"):
        service._discover_one(
            workspace_id="workspace",
            source=DiscoverySource(
                kind="liepin_cdp",
                source_name="猎聘",
                query="AI",
            ),
        )


def test_liepin_http_skips_cdp_tier_when_browser_forbidden() -> None:
    """liepin_http is pure HTTP: allow_browser=False must not drop it."""
    attempted: list[str] = []

    class RecordingImports:
        def import_connector(self, workspace_id, connector, **kwargs):
            attempted.append(type(connector).__name__)
            return ImportSummary(0, 0, 0, ())

    service = JobDiscoveryService(RecordingImports())
    service._discover_one(
        workspace_id="workspace",
        source=DiscoverySource(
            kind="liepin_http",
            source_name="猎聘",
            query="AI应用工程师",
            location="上海",
        ),
        allow_browser=False,
    )

    assert attempted == ["LiepinPureHttpConnector"]  # no CDP fallback


def test_liepin_http_allows_cdp_fallback_when_browser_permitted() -> None:
    attempted: list[tuple[str, int]] = []

    class FlakyImports:
        def import_connector(self, workspace_id, connector, **kwargs):
            name = type(connector).__name__
            enrich_limit = kwargs.get("enrich_limit", 0)
            attempted.append((name, enrich_limit))
            if name != "LiepinConnector":
                raise RuntimeError("blocked")
            return ImportSummary(0, 0, 0, ())

    service = JobDiscoveryService(FlakyImports())
    service._discover_one(
        workspace_id="workspace",
        source=DiscoverySource(
            kind="liepin_http",
            source_name="猎聘",
            query="AI",
            location="上海",
        ),
        allow_browser=True,
    )

    assert attempted == [
        ("LiepinPureHttpConnector", 0),
        ("LiepinConnector", 3),
    ]


def test_import_connector_uses_optional_enricher_without_platform_dependency(
    tmp_path,
) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    workspace = WorkspaceService(database).create("enrichment")
    service = JobImportService(JobRepository(database))

    class EnrichingConnector:
        def fetch(self):
            return [raw_job(payload={"description": ""})]

        def enrich(self, records, *, limit):
            assert limit == 1
            record = records[0]
            return [
                record.model_copy(
                    update={
                        "payload": {
                            **dict(record.payload),
                            "description": "Python RAG Agent",
                            "description_source_url": "https://careers.example.com/jobs/1",
                            "detail_level": "detail_page",
                        }
                    }
                )
            ]

    result = service.import_connector(
        workspace.workspace_id,
        EnrichingConnector(),
        fetched_at=NOW,
        enrich_limit=1,
    )

    assert result.jobs[0].description == "Python RAG Agent"
    assert result.jobs[0].source.detail_level is JobDetailLevel.DETAIL_PAGE
    assert (
        result.jobs[0].source.description_source_url
        == "https://careers.example.com/jobs/1"
    )
    assert result.jobs[0].source.description_fetched_at == NOW


def test_detail_page_evidence_requires_url_and_timestamp() -> None:
    with pytest.raises(ValueError, match="detail_page evidence requires"):
        SourceEvidence(
            source_kind=SourceKind.CAREER_SITE,
            source_name="猎聘",
            source_url="https://www.liepin.com/search",
            fetched_at=NOW,
            detail_level=JobDetailLevel.DETAIL_PAGE,
        )


def raw_job(**overrides: object) -> RawJobRecord:
    payload: dict[str, object] = {
        "title": "AI应用工程师",
        "company": "星河科技",
        "description": "Python RAG Agent，1-3年，20-35K",
        "location": "杭州",
        "url": "https://careers.example.com/jobs/1",
        "published_at": "2026-07-27T00:00:00Z",
    }
    payload.update(overrides.pop("payload", {}))
    values: dict[str, object] = {
        "source_kind": SourceKind.CAREER_SITE,
        "source_name": "星河科技官网",
        "source_url": "https://careers.example.com",
        "external_id": "1",
        "payload": payload,
    }
    values.update(overrides)
    return RawJobRecord(**values)


def test_csv_and_json_import_produce_raw_records() -> None:
    csv_records = parse_csv(
        "id,title,company,url\n1,AI工程师,甲公司,https://a.example/jobs/1\n",
        source_name="export",
    )
    json_records = parse_json(
        '[{"id":"2","title":"RAG工程师","company":"乙公司",'
        '"url":"https://b.example/jobs/2"}]',
        source_name="export",
    )

    assert csv_records[0].source_kind == SourceKind.CSV
    assert json_records[0].source_kind == SourceKind.JSON
    assert {csv_records[0].external_id, json_records[0].external_id} == {"1", "2"}


def test_normalization_preserves_source_liveness_and_structured_ranges() -> None:
    job = normalize_job(raw_job(), fetched_at=NOW)

    assert job.title == "AI应用工程师"
    assert job.locations == ("杭州",)
    assert (job.salary_min_k, job.salary_max_k) == (20, 35)
    assert (job.experience_min_years, job.experience_max_years) == (1, 3)
    assert job.source.liveness == JobLiveness.ACTIVE
    assert job.source.detail_level is JobDetailLevel.STRUCTURED_SOURCE
    assert job.source.source_url == "https://careers.example.com"
    assert job.salary is not None
    assert job.salary.raw_text == "20-35K"
    assert job.salary.normalized_annual_min == 240_000
    assert job.recruitment_track is RecruitmentTrack.UNKNOWN
    assert job.employment_type is EmploymentType.UNKNOWN


def test_annual_salary_mirror_is_monthly_derived_not_amount_divided_by_1000() -> None:
    job = normalize_job(
        raw_job(
            payload={
                "description": "Python RAG Agent，3-5年，30-45万/年",
            }
        ),
        fetched_at=NOW,
    )

    # 30万/年 is 25K/month; the legacy mirror must never become 300K/month.
    assert job.salary is not None
    assert job.salary.period is SalaryPeriod.YEAR
    assert job.salary_min_k == 25
    assert job.salary_max_k == 37


def test_normalization_keeps_recruitment_and_employment_dimensions_separate() -> None:
    campus_intern = normalize_job(
        raw_job(
            payload={
                "title": "大模型应用工程师实习生",
                "description": "2027届校园招聘，实习岗位",
                "recruitment_track": "campus",
            }
        ),
        fetched_at=NOW,
    )
    social_full_time = normalize_job(
        raw_job(
            payload={
                "title": "AI应用工程师",
                "description": "社会招聘，全职正式岗位",
                "recruitment_track": "social",
                "employment_type": "FullTime",
            }
        ),
        fetched_at=NOW,
    )

    assert campus_intern.recruitment_track is RecruitmentTrack.CAMPUS
    assert campus_intern.employment_type is EmploymentType.INTERNSHIP
    assert social_full_time.recruitment_track is RecruitmentTrack.SOCIAL
    assert social_full_time.employment_type is EmploymentType.FULL_TIME


def test_unknown_job_is_not_assumed_to_be_social_or_full_time() -> None:
    job = normalize_job(
        raw_job(payload={"title": "AI应用工程师", "description": "负责RAG系统"}),
        fetched_at=NOW,
    )

    assert job.recruitment_track is RecruitmentTrack.UNKNOWN
    assert job.employment_type is EmploymentType.UNKNOWN


def test_schema_org_employment_type_is_normalized() -> None:
    job = normalize_job(
        raw_job(payload={"employmentType": "FULL_TIME"}),
        fetched_at=NOW,
    )

    assert job.employment_type is EmploymentType.FULL_TIME


def test_technical_contract_word_does_not_mean_contract_employment() -> None:
    job = normalize_job(
        raw_job(
            payload={
                "title": "AI应用工程师",
                "description": "负责 API contract 与 Pydantic schema 设计",
            }
        ),
        fetched_at=NOW,
    )

    assert job.employment_type is EmploymentType.UNKNOWN


def test_chinese_salary_keeps_raw_period_and_annual_normalization() -> None:
    monthly = normalize_job(
        raw_job(payload={"description": "薪资20-30K·13薪"}),
        fetched_at=NOW,
    )
    annual = normalize_job(
        raw_job(payload={"description": "薪资30-45万/年"}),
        fetched_at=NOW,
    )

    assert monthly.salary is not None
    assert monthly.salary.months_per_year == 13
    assert monthly.salary.normalized_annual_max == 390_000
    assert annual.salary is not None
    assert annual.salary.period == "year"
    assert annual.salary.normalized_annual_min == 300_000


def test_old_and_closed_jobs_are_not_reported_as_active() -> None:
    stale = normalize_job(
        raw_job(payload={"published_at": "2026-01-01T00:00:00Z"}),
        fetched_at=NOW,
    )
    closed = normalize_job(
        raw_job(payload={"closed": True}),
        fetched_at=NOW,
    )

    assert stale.source.liveness == JobLiveness.STALE
    assert closed.source.liveness == JobLiveness.CLOSED


def test_import_deduplicates_and_versions_only_content_changes(tmp_path) -> None:
    database = Database(tmp_path / "jobs.db")
    database.migrate()
    workspace = WorkspaceService(database).create("test")
    repository = JobRepository(database)
    service = JobImportService(repository)

    first = service.import_records(
        workspace.workspace_id, [raw_job(), raw_job()], fetched_at=NOW
    )
    same = service.import_records(workspace.workspace_id, [raw_job()], fetched_at=NOW)
    changed = service.import_records(
        workspace.workspace_id,
        [raw_job(payload={"description": "Python RAG Agent，新增MCP能力"})],
        fetched_at=NOW,
    )

    assert (first.discovered, first.unique, first.versions_created) == (2, 1, 1)
    assert same.versions_created == 0
    assert changed.versions_created == 1
    assert len(repository.list(workspace.workspace_id)) == 1
    with database.connect() as connection:
        version_count = connection.execute(
            "SELECT count(*) FROM job_versions"
        ).fetchone()[0]
    assert version_count == 2


def test_repository_repairs_legacy_boss_job_classification(tmp_path) -> None:
    database = Database(tmp_path / "jobs.db")
    database.migrate()
    workspace = WorkspaceService(database).create("Legacy BOSS")
    repository = JobRepository(database)
    legacy = normalize_job(
        raw_job(
            source_name="BOSS直聘·杭州",
            external_id="legacy-boss",
            payload={
                "title": "AI应用工程师",
                "description": "Python RAG Agent",
            },
        )
    )
    assert legacy.employment_type == "unknown"

    repository.upsert(workspace.workspace_id, legacy)
    repaired = repository.list(workspace.workspace_id)[0]

    assert repaired.recruitment_track == "social"
    assert repaired.employment_type == "full_time"


def test_reappearing_content_does_not_crash_or_create_duplicate_version(
    tmp_path,
) -> None:
    database = Database(tmp_path / "jobs.db")
    database.migrate()
    workspace = WorkspaceService(database).create("test")
    service = JobImportService(JobRepository(database))

    original = raw_job()
    changed = raw_job(payload={"description": "Python RAG Agent，新增MCP能力"})
    first = service.import_records(workspace.workspace_id, [original], fetched_at=NOW)
    second = service.import_records(workspace.workspace_id, [changed], fetched_at=NOW)
    reverted = service.import_records(
        workspace.workspace_id, [original], fetched_at=NOW
    )

    assert first.versions_created == 1
    assert second.versions_created == 1
    assert reverted.versions_created == 0
    with database.connect() as connection:
        version_count = connection.execute(
            "SELECT count(*) FROM job_versions"
        ).fetchone()[0]
    assert version_count == 2


def test_cross_source_duplicate_keeps_two_source_records(tmp_path) -> None:
    database = Database(tmp_path / "jobs.db")
    database.migrate()
    workspace = WorkspaceService(database).create("test")
    repository = JobRepository(database)
    service = JobImportService(repository)
    second = raw_job(
        source_name="聚合来源",
        source_url="https://jobs.example.net",
        external_id="other-42",
        payload={"url": "https://jobs.example.net/apply/42"},
    )

    service.import_records(
        workspace.workspace_id,
        [raw_job(), second],
        fetched_at=NOW,
    )

    jobs = repository.list(workspace.workspace_id)
    records = repository.source_records(
        workspace_id=workspace.workspace_id,
        job_id=jobs[0].job_id,
    )
    assert len(jobs) == 1
    assert {record.source_name for record in records} == {
        "星河科技官网",
        "聚合来源",
    }

    repository.mark_missing_closed(
        workspace_id=workspace.workspace_id,
        source_name="星河科技官网",
        observed_job_ids=set(),
        observed_at=NOW,
    )
    assert (
        repository.get(
            workspace_id=workspace.workspace_id,
            job_id=jobs[0].job_id,
        ).source.liveness
        == JobLiveness.ACTIVE
    )

    repository.mark_missing_closed(
        workspace_id=workspace.workspace_id,
        source_name="聚合来源",
        observed_job_ids=set(),
        observed_at=NOW,
    )
    assert (
        repository.get(
            workspace_id=workspace.workspace_id,
            job_id=jobs[0].job_id,
        ).source.liveness
        == JobLiveness.CLOSED
    )
