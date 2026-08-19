from __future__ import annotations

import json
from datetime import UTC, datetime

from jobfindsme.contracts import JobLiveness, SalaryPeriod
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.parsers import parse_json
from jobfindsme.importing.repository import JobRepository
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def _legacy_annual_payload() -> dict[str, object]:
    job = normalize_job(
        parse_json(
            '[{"id":"legacy-annual","title":"AI应用工程师",'
            '"company":"旧数据公司","location":"上海",'
            '"description":"Python RAG Agent，30-45万/年",'
            '"url":"https://example.com/legacy-annual"}]',
            source_name="BOSS直聘·上海",
        )[0],
        fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    payload = json.loads(job.model_dump_json())
    payload["salary_min_k"] = 300
    payload["salary_max_k"] = 450
    return payload


def _insert_legacy_job(database: Database, workspace_id: str) -> str:
    payload = _legacy_annual_payload()
    source = payload["source"]
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                workspace_id, job_id, fingerprint, content_hash, payload_json,
                source_name, external_id, liveness, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                payload["job_id"],
                payload["fingerprint"],
                payload["content_hash"],
                json.dumps(payload, ensure_ascii=False),
                source["source_name"],
                payload["external_id"],
                source["liveness"],
                source["fetched_at"],
            ),
        )
        connection.execute(
            """
            INSERT INTO job_source_records (
                record_id, workspace_id, job_id, source_name, external_id,
                source_url, apply_url, liveness, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-record",
                workspace_id,
                payload["job_id"],
                source["source_name"],
                payload["external_id"],
                source["source_url"],
                payload["apply_url"],
                source["liveness"],
                source["fetched_at"],
            ),
        )
    return str(payload["job_id"])


def test_repository_repairs_legacy_annual_salary_before_validation(tmp_path) -> None:
    database = Database(tmp_path / "legacy.db")
    database.migrate()
    workspace = WorkspaceService(database).create("legacy")
    job_id = _insert_legacy_job(database, workspace.workspace_id)
    repository = JobRepository(database)

    listed = repository.list(workspace.workspace_id)[0]
    loaded = repository.get(workspace_id=workspace.workspace_id, job_id=job_id)

    assert listed.salary is not None
    assert listed.salary.period is SalaryPeriod.YEAR
    assert (listed.salary_min_k, listed.salary_max_k) == (25, 37)
    assert loaded.model_dump() == listed.model_dump()


def test_compatibility_loader_covers_failure_and_close_paths(tmp_path) -> None:
    database = Database(tmp_path / "legacy-state.db")
    database.migrate()
    workspace = WorkspaceService(database).create("legacy")
    job_id = _insert_legacy_job(database, workspace.workspace_id)
    repository = JobRepository(database)

    assert (
        repository.mark_source_unknown(
            workspace_id=workspace.workspace_id,
            source_name="BOSS直聘·上海",
            observed_at=datetime(2026, 8, 2, tzinfo=UTC),
        )
        == 1
    )
    unknown = repository.get(workspace_id=workspace.workspace_id, job_id=job_id)
    assert unknown.source.liveness is JobLiveness.UNKNOWN
    assert (unknown.salary_min_k, unknown.salary_max_k) == (25, 37)

    assert (
        repository.mark_missing_closed(
            workspace_id=workspace.workspace_id,
            source_name="BOSS直聘·上海",
            observed_job_ids=set(),
            observed_at=datetime(2026, 8, 3, tzinfo=UTC),
        )
        == 1
    )
    closed = repository.get(workspace_id=workspace.workspace_id, job_id=job_id)
    assert closed.source.liveness is JobLiveness.CLOSED
    assert (closed.salary_min_k, closed.salary_max_k) == (25, 37)


def test_same_source_out_of_order_import_keeps_newest_observation(tmp_path) -> None:
    database = Database(tmp_path / "ordering.db")
    database.migrate()
    workspace = WorkspaceService(database).create("ordering")
    repository = JobRepository(database)
    older = normalize_job(
        parse_json(
            '[{"id":"same-source","title":"AI应用工程师",'
            '"company":"同源公司","location":"上海",'
            '"description":"旧 JD Python RAG",'
            '"url":"https://example.com/same-source"}]',
            source_name="猎聘",
        )[0],
        fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    newer = normalize_job(
        parse_json(
            '[{"id":"same-source","title":"AI应用工程师",'
            '"company":"同源公司","location":"上海",'
            '"description":"新 JD Python RAG Agent",'
            '"url":"https://example.com/same-source"}]',
            source_name="猎聘",
        )[0],
        fetched_at=datetime(2026, 8, 2, tzinfo=UTC),
    )

    repository.upsert(workspace.workspace_id, newer)
    repository.upsert(workspace.workspace_id, older)

    current = repository.list(workspace.workspace_id)[0]
    assert current.source.fetched_at == newer.source.fetched_at
    assert current.content_hash == newer.content_hash
