from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from jobfindsme.connectors import AshbyConnector, ConnectorPolicy
from jobfindsme.core import JobFindsMeCore

ROOT = Path(__file__).parents[2]
SNAPSHOT = ROOT / "data" / "fixtures" / "airwallex_ashby_china_2026-07-28.json"
REPORT = ROOT / "reports" / "field-trials" / "airwallex-china-2026-07-28.json"


class SnapshotTransport:
    def get(self, url: str) -> bytes:
        assert url == (
            "https://api.ashbyhq.com/posting-api/job-board/"
            "airwallex?includeCompensation=true"
        )
        return SNAPSHOT.read_bytes()


def test_airwallex_china_snapshot_runs_through_import_and_identity(tmp_path) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert (
        snapshot["capture"]["raw_response_sha256"]
        == report["source"]["raw_response_sha256"]
    )

    connector = AshbyConnector(
        "airwallex",
        transport=SnapshotTransport(),
        policy=ConnectorPolicy(public_access=True, robots_allowed=True),
        source_name="Airwallex",
    )
    core = JobFindsMeCore(tmp_path / "china-source.db")
    workspace = core.create_workspace("china source")
    fetched_at = datetime(2026, 7, 28, tzinfo=UTC)

    first = core.job_imports.import_connector(
        workspace.workspace_id,
        connector,
        fetched_at=fetched_at,
    )
    second = core.job_imports.import_connector(
        workspace.workspace_id,
        connector,
        fetched_at=fetched_at,
    )
    jobs = core.jobs.list(workspace.workspace_id)

    assert (first.discovered, first.unique) == (3, 3)
    assert (second.discovered, second.unique) == (3, 3)
    assert len(jobs) == 3
    assert {location for job in jobs for location in job.locations} == {
        "CN - Shanghai",
        "CN - Shenzhen",
    }
    assert all(job.company == "Airwallex" for job in jobs)
    assert all(job.apply_url.endswith("/application") for job in jobs)
    assert len({job.fingerprint for job in jobs}) == 3


def test_airwallex_snapshot_and_report_are_metadata_only() -> None:
    snapshot_bytes = SNAPSHOT.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert hashlib.sha256(snapshot_bytes).hexdigest()
    assert all(not job["descriptionPlain"] for job in snapshot["jobs"])
    assert report["observed"]["china_jobs"] == 35
    assert report["validation"]["normalization_tested"] is True
    assert report["limitations"]
