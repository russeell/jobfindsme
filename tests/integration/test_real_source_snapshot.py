from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from jobfindsme.connectors import ConnectorPolicy, GreenhouseConnector
from jobfindsme.core import JobFindsMeCore

ROOT = Path(__file__).parents[2]
SNAPSHOT = ROOT / "data" / "fixtures" / "scaleai_greenhouse_2026-07-28.json"
TRIAL = ROOT / "data" / "eval" / "field_trial_v0.1.json"
REPORT = ROOT / "reports" / "field-trials" / "initial-2026-07-28.json"


class CapturedTransport:
    def get(self, url: str) -> bytes:
        assert url == (
            "https://boards-api.greenhouse.io/v1/boards/scaleai/jobs?content=true"
        )
        document = json.loads(SNAPSHOT.read_text())
        return json.dumps({"jobs": document["jobs"]}).encode()


def test_real_public_source_snapshot_runs_through_complete_core_flow(
    tmp_path,
) -> None:
    expected = json.loads(TRIAL.read_text())
    snapshot_hash = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    assert snapshot_hash == expected["source_sha256"]

    connector = GreenhouseConnector(
        "scaleai",
        transport=CapturedTransport(),
        policy=ConnectorPolicy(public_access=True, robots_allowed=True),
    )
    core = JobFindsMeCore(tmp_path / "field.db")
    workspace = core.create_workspace("field trial")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI Advisory",
        target_roles=expected["search_plan"]["target_roles"],
        locations=expected["search_plan"]["locations"],
    )
    summary = core.job_imports.import_connector(
        workspace.workspace_id,
        connector,
        fetched_at=datetime(2026, 7, 28, tzinfo=UTC),
    )
    matches = core.match_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
    )

    assert summary.discovered == expected["expected"]["discovered"]
    assert summary.unique == expected["expected"]["unique"]
    assert [item.job.external_id for item in matches] == expected["expected"][
        "matched_external_ids"
    ]
    assert all(
        item.job.apply_url.startswith("https://job-boards.greenhouse.io/")
        for item in matches
    )


def test_field_report_does_not_claim_time_or_production_evidence() -> None:
    report = json.loads(REPORT.read_text())

    assert report["claims"]["real_public_source_flow_validated"] is True
    assert report["claims"]["one_to_two_week_personal_use_completed"] is False
    assert report["claims"]["production_field_performance_claimed"] is False
