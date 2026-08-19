from __future__ import annotations

import json
from datetime import datetime

from jobfindsme.contracts import (
    EmploymentType,
    JobLiveness,
    JobPosting,
    JobSourceRecord,
    RecruitmentTrack,
)
from jobfindsme.storage import Database

_SOURCE_RANK = {
    "BOSS直聘": 0,
    "猎聘": 1,
    "智联招聘": 2,
    "前程无忧": 3,
}


def _liveness_rank(liveness: JobLiveness) -> int:
    return {
        JobLiveness.ACTIVE: 3,
        JobLiveness.UNKNOWN: 2,
        JobLiveness.STALE: 1,
        JobLiveness.CLOSED: 0,
    }.get(liveness, 1)


def _canonical_winner(left: JobPosting, right: JobPosting) -> JobPosting:
    """Deterministic canonical pick for the same fingerprint from two sources.

    Same source: the newest observation wins (content refresh must propagate).
    Different sources: richer detail wins, ties broken by a stable source
    priority, never by thread completion order.
    """
    if left.source.source_name == right.source.source_name:
        return right

    def quality(job: JobPosting) -> tuple[int, int, int, int]:
        return (
            _liveness_rank(job.source.liveness),
            len(job.description),
            int(job.salary is not None),
            int(bool(job.apply_url)),
        )

    left_quality, right_quality = quality(left), quality(right)
    if left_quality != right_quality:
        return left if left_quality > right_quality else right
    left_rank = _SOURCE_RANK.get(left.source.source_name, 99)
    right_rank = _SOURCE_RANK.get(right.source.source_name, 99)
    return left if left_rank <= right_rank else right


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, workspace_id: str, job: JobPosting) -> bool:
        """Store current job and append a version only when content changed."""
        payload = job.model_dump_json()
        with self.database.connect() as connection:
            existing_row = connection.execute(
                "SELECT payload_json, content_hash FROM jobs "
                "WHERE workspace_id = ? AND job_id = ?",
                (workspace_id, job.job_id),
            ).fetchone()
            existing = (
                _repair_legacy_boss_classification(
                    JobPosting.model_validate_json(existing_row["payload_json"])
                )
                if existing_row
                else None
            )
            winner = _canonical_winner(existing, job) if existing else job
            winner_payload = winner.model_dump_json()
            if existing is None:
                changed = True
                connection.execute(
                    """
                    INSERT INTO jobs (
                        workspace_id, job_id, fingerprint, content_hash, payload_json,
                        source_name, external_id, liveness, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        job.job_id,
                        job.fingerprint,
                        job.content_hash,
                        winner_payload,
                        winner.source.source_name,
                        winner.external_id,
                        winner.source.liveness,
                        winner.source.fetched_at.isoformat(),
                    ),
                )
            elif winner is job:
                changed = existing_row["content_hash"] != job.content_hash
                connection.execute(
                    """
                    UPDATE jobs SET
                        content_hash = ?, payload_json = ?, source_name = ?,
                        external_id = ?, liveness = ?, fetched_at = ?
                    WHERE workspace_id = ? AND job_id = ?
                    """,
                    (
                        job.content_hash,
                        winner_payload,
                        job.source.source_name,
                        job.external_id,
                        job.source.liveness,
                        job.source.fetched_at.isoformat(),
                        workspace_id,
                        job.job_id,
                    ),
                )
            else:
                # Lower-quality source: keep the canonical row untouched; only
                # the source record below records this observation.
                changed = False
            version_created = False
            if changed:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO job_versions (
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
                version_created = cursor.rowcount == 1
            record_id = _source_record_id(
                workspace_id,
                job.source.source_name,
                job.external_id,
            )
            connection.execute(
                """
                INSERT INTO job_source_records (
                    record_id, workspace_id, job_id, source_name, external_id,
                    source_url, apply_url, liveness, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, source_name, external_id) DO UPDATE SET
                    job_id = excluded.job_id,
                    source_url = excluded.source_url,
                    apply_url = excluded.apply_url,
                    liveness = excluded.liveness,
                    observed_at = excluded.observed_at
                """,
                (
                    record_id,
                    workspace_id,
                    job.job_id,
                    job.source.source_name,
                    job.external_id,
                    job.source.source_url,
                    job.apply_url,
                    job.source.liveness,
                    job.source.fetched_at.isoformat(),
                ),
            )
        return version_created

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
            _repair_legacy_boss_classification(
                JobPosting.model_validate(json.loads(row["payload_json"]))
            )
            for row in rows
        ]

    def has_source_jobs(self, *, workspace_id: str, source_name: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM job_source_records
                WHERE workspace_id = ? AND source_name = ?
                  AND liveness != 'closed'
                LIMIT 1
                """,
                (workspace_id, source_name),
            ).fetchone()
        return row is not None

    def mark_source_unknown(
        self,
        *,
        workspace_id: str,
        source_name: str,
        observed_at: datetime,
    ) -> int:
        """Keep the last successful snapshot available after a refresh failure."""

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT j.job_id AS job_id, j.payload_json AS payload_json
                FROM job_source_records r
                JOIN jobs j
                  ON j.workspace_id = r.workspace_id AND j.job_id = r.job_id
                WHERE r.workspace_id = ? AND r.source_name = ?
                  AND r.liveness != 'closed'
                """,
                (workspace_id, source_name),
            ).fetchall()
            for row in rows:
                job = JobPosting.model_validate_json(row["payload_json"])
                updated = job.model_copy(
                    update={
                        "source": job.source.model_copy(
                            update={"liveness": JobLiveness.UNKNOWN}
                        )
                    }
                )
                connection.execute(
                    """
                    UPDATE jobs SET payload_json = ?, liveness = ?
                    WHERE workspace_id = ? AND job_id = ?
                    """,
                    (
                        updated.model_dump_json(),
                        JobLiveness.UNKNOWN,
                        workspace_id,
                        job.job_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE job_source_records SET liveness = ?, observed_at = ?
                    WHERE workspace_id = ? AND source_name = ? AND job_id = ?
                    """,
                    (
                        JobLiveness.UNKNOWN,
                        observed_at.isoformat(),
                        workspace_id,
                        source_name,
                        job.job_id,
                    ),
                )
        return len(rows)

    def get(self, *, workspace_id: str, job_id: str) -> JobPosting:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM jobs
                WHERE workspace_id = ? AND job_id = ?
                """,
                (workspace_id, job_id),
            ).fetchone()
        if row is None:
            raise LookupError(job_id)
        return _repair_legacy_boss_classification(
            JobPosting.model_validate(json.loads(row["payload_json"]))
        )

    def source_records(
        self,
        *,
        workspace_id: str,
        job_id: str,
    ) -> tuple[JobSourceRecord, ...]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM job_source_records
                WHERE workspace_id = ? AND job_id = ?
                ORDER BY observed_at DESC, record_id
                """,
                (workspace_id, job_id),
            ).fetchall()
        return tuple(
            JobSourceRecord(
                record_id=row["record_id"],
                workspace_id=row["workspace_id"],
                job_id=row["job_id"],
                source_name=row["source_name"],
                external_id=row["external_id"],
                source_url=row["source_url"],
                apply_url=row["apply_url"],
                liveness=row["liveness"],
                observed_at=datetime.fromisoformat(row["observed_at"]),
            )
            for row in rows
        )

    def mark_missing_closed(
        self,
        *,
        workspace_id: str,
        source_name: str,
        observed_job_ids: set[str],
        observed_at: datetime,
    ) -> int:
        """Close source records absent from a successful complete refresh."""
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT job_id FROM job_source_records
                WHERE workspace_id = ? AND source_name = ?
                  AND liveness != 'closed'
                """,
                (workspace_id, source_name),
            ).fetchall()
            missing_ids = {
                row["job_id"] for row in rows if row["job_id"] not in observed_job_ids
            }
            if not missing_ids:
                return 0
            placeholders = ",".join("?" for _ in missing_ids)
            connection.execute(
                f"""
                UPDATE job_source_records
                SET liveness = 'closed', observed_at = ?
                WHERE workspace_id = ? AND source_name = ?
                  AND job_id IN ({placeholders})
                """,
                (
                    observed_at.isoformat(),
                    workspace_id,
                    source_name,
                    *sorted(missing_ids),
                ),
            )
            for job_id in sorted(missing_ids):
                liveness_rows = connection.execute(
                    """
                    SELECT liveness FROM job_source_records
                    WHERE workspace_id = ? AND job_id = ?
                    """,
                    (workspace_id, job_id),
                ).fetchall()
                aggregate = _aggregate_liveness(
                    [JobLiveness(row["liveness"]) for row in liveness_rows]
                )
                row = connection.execute(
                    """
                    SELECT payload_json FROM jobs
                    WHERE workspace_id = ? AND job_id = ?
                    """,
                    (workspace_id, job_id),
                ).fetchone()
                job = JobPosting.model_validate_json(row["payload_json"])
                updated = job.model_copy(
                    update={
                        "source": job.source.model_copy(
                            update={
                                "liveness": aggregate,
                                "fetched_at": observed_at,
                            }
                        )
                    }
                )
                updated = updated.model_copy(
                    update={"content_hash": _closed_content_hash(updated)}
                )
                connection.execute(
                    """
                    UPDATE jobs SET
                        payload_json = ?, content_hash = ?, liveness = ?,
                        fetched_at = ?
                    WHERE workspace_id = ? AND job_id = ?
                    """,
                    (
                        updated.model_dump_json(),
                        updated.content_hash,
                        aggregate,
                        observed_at.isoformat(),
                        workspace_id,
                        job_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO job_versions (
                        workspace_id, job_id, content_hash, payload_json, observed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        workspace_id,
                        job_id,
                        updated.content_hash,
                        updated.model_dump_json(),
                        observed_at.isoformat(),
                    ),
                )
        return len(missing_ids)


def _closed_content_hash(job: JobPosting) -> str:
    import hashlib

    value = f"{job.content_hash}|closed|{job.source.fetched_at.isoformat()}"
    return hashlib.sha256(value.encode()).hexdigest()


def _source_record_id(workspace_id: str, source_name: str, external_id: str) -> str:
    import hashlib

    value = f"{workspace_id}\0{source_name.casefold()}\0{external_id}"
    return f"record_{hashlib.sha256(value.encode()).hexdigest()[:32]}"


def _aggregate_liveness(values: list[JobLiveness]) -> JobLiveness:
    for preferred in (
        JobLiveness.ACTIVE,
        JobLiveness.UNKNOWN,
        JobLiveness.STALE,
        JobLiveness.CLOSED,
    ):
        if preferred in values:
            return preferred
    return JobLiveness.UNKNOWN


def _repair_legacy_boss_classification(job: JobPosting) -> JobPosting:
    """Interpret cached BOSS rows written before explicit type fields existed."""

    if not job.source.source_name.startswith("BOSS直聘"):
        return job
    text = f"{job.title} {job.description}".casefold()
    recruitment_track = job.recruitment_track
    if recruitment_track is RecruitmentTrack.UNKNOWN:
        recruitment_track = (
            RecruitmentTrack.CAMPUS
            if any(term in text for term in ("校招", "校园", "应届"))
            else RecruitmentTrack.SOCIAL
        )
    employment_type = job.employment_type
    if employment_type is EmploymentType.UNKNOWN:
        if any(term in text for term in ("实习", "intern")):
            employment_type = EmploymentType.INTERNSHIP
        elif "兼职" in text:
            employment_type = EmploymentType.PART_TIME
        elif "合同" in text:
            employment_type = EmploymentType.CONTRACT
        else:
            employment_type = EmploymentType.FULL_TIME
    return job.model_copy(
        update={
            "recruitment_track": recruitment_track,
            "employment_type": employment_type,
        }
    )
