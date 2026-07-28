from __future__ import annotations

from datetime import UTC, datetime

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import JobLiveness, SourceKind
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.parsers import parse_csv, parse_json
from jobfindsme.importing.repository import JobRepository
from jobfindsme.importing.service import JobImportService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService

NOW = datetime(2026, 7, 28, tzinfo=UTC)


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
    return RawJobRecord(
        source_kind=SourceKind.CAREER_SITE,
        source_name="星河科技官网",
        source_url="https://careers.example.com",
        external_id="1",
        payload=payload,
        **overrides,
    )


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
    assert job.source.source_url == "https://careers.example.com"


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
