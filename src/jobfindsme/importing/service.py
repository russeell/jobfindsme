from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from jobfindsme.connectors.base import Connector, RawJobRecord
from jobfindsme.contracts import JobPosting
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.repository import JobRepository


@dataclass(frozen=True)
class ImportSummary:
    discovered: int
    unique: int
    versions_created: int
    jobs: tuple[JobPosting, ...]


class JobImportService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def import_connector(
        self,
        workspace_id: str,
        connector: Connector,
        *,
        fetched_at: datetime | None = None,
    ) -> ImportSummary:
        return self.import_records(
            workspace_id, connector.fetch(), fetched_at=fetched_at
        )

    def import_records(
        self,
        workspace_id: str,
        records: Iterable[RawJobRecord],
        *,
        fetched_at: datetime | None = None,
    ) -> ImportSummary:
        raw_records = list(records)
        unique: dict[str, JobPosting] = {}
        for raw in raw_records:
            job = normalize_job(raw, fetched_at=fetched_at)
            unique[job.fingerprint] = job
        versions = sum(
            self.repository.upsert(workspace_id, job) for job in unique.values()
        )
        return ImportSummary(
            discovered=len(raw_records),
            unique=len(unique),
            versions_created=versions,
            jobs=tuple(unique.values()),
        )
