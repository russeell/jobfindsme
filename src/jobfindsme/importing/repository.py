from __future__ import annotations

import json

from jobfindsme.contracts import JobPosting
from jobfindsme.storage import Database


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, workspace_id: str, job: JobPosting) -> bool:
        """Store current job and append a version only when content changed."""
        payload = job.model_dump_json()
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT content_hash FROM jobs WHERE workspace_id = ? AND job_id = ?",
                (workspace_id, job.job_id),
            ).fetchone()
            changed = existing is None or existing["content_hash"] != job.content_hash
            connection.execute(
                """
                INSERT INTO jobs (
                    workspace_id, job_id, fingerprint, content_hash, payload_json,
                    source_name, external_id, liveness, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, job_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    payload_json = excluded.payload_json,
                    source_name = excluded.source_name,
                    external_id = excluded.external_id,
                    liveness = excluded.liveness,
                    fetched_at = excluded.fetched_at
                """,
                (
                    workspace_id,
                    job.job_id,
                    job.fingerprint,
                    job.content_hash,
                    payload,
                    job.source.source_name,
                    job.external_id,
                    job.source.liveness,
                    job.source.fetched_at.isoformat(),
                ),
            )
            if changed:
                connection.execute(
                    """
                    INSERT INTO job_versions (
                        workspace_id, job_id, content_hash, payload_json, observed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        job.job_id,
                        job.content_hash,
                        payload,
                        job.source.fetched_at.isoformat(),
                    ),
                )
        return changed

    def list(self, workspace_id: str) -> list[JobPosting]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM jobs
                WHERE workspace_id = ?
                ORDER BY fetched_at DESC, job_id
                """,
                (workspace_id,),
            ).fetchall()
        return [
            JobPosting.model_validate(json.loads(row["payload_json"])) for row in rows
        ]
