#!/usr/bin/env python3
"""Verify that an installed package can read a representative 0.11.0 DB row."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.parsers import parse_json
from jobfindsme.importing.repository import JobRepository
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="jobfindsme-legacy-smoke-") as directory:
        database = Database(Path(directory) / "jobfindsme.db")
        database.migrate()
        workspace = WorkspaceService(database).create("0.11.0 compatibility")
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
        # This is the pre-0.12 annual-salary mirror bug: 300/450 were
        # persisted as monthly K values instead of 25/37.
        payload["salary_min_k"] = 300
        payload["salary_max_k"] = 450
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
                    workspace.workspace_id,
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
                    "legacy-smoke-record",
                    workspace.workspace_id,
                    payload["job_id"],
                    source["source_name"],
                    payload["external_id"],
                    source["source_url"],
                    payload["apply_url"],
                    source["liveness"],
                    source["fetched_at"],
                ),
            )

        loaded = JobRepository(database).get(
            workspace_id=workspace.workspace_id,
            job_id=payload["job_id"],
        )
        assert loaded.salary_min_k == 25
        assert loaded.salary_max_k == 37
        print("legacy 0.11.0 salary payload: PASS")


if __name__ == "__main__":
    main()
