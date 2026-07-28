from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from jobfindsme.contracts import DiscoverySource
from jobfindsme.core import JobFindsMeCore
from jobfindsme.importing import JobDiscoveryService
from jobfindsme.importing.parsers import parse_json
from jobfindsme.monitoring import LocalMonitorRunner

NOW = datetime(2026, 7, 28, 8, 30, tzinfo=UTC)


def configured_core(tmp_path, *, enabled: bool = True):
    core = JobFindsMeCore(tmp_path / "monitor.db")
    workspace = core.create_workspace("monitor")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            """
            [{
              "id": "1",
              "title": "AI应用工程师",
              "company": "示例",
              "description": "Python RAG Agent",
              "url": "https://example.com/jobs/1"
            }]
            """,
            source_name="fixture",
        ),
    )
    core.configure_monitor(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        enabled=enabled,
        interval_hours=24,
    )
    return core, workspace, plan


def test_monitor_runs_enabled_plan_once_per_time_slot(tmp_path) -> None:
    core, workspace, plan = configured_core(tmp_path)
    notifications = []
    runner = LocalMonitorRunner(core.database)

    def search(workspace_id, plan_id):
        return core.match_jobs(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )

    first = runner.run_due(
        now=NOW,
        search=search,
        notify=notifications.append,
    )
    duplicate = runner.run_due(
        now=NOW + timedelta(minutes=5),
        search=search,
        notify=notifications.append,
    )

    assert first[0].status == "success"
    assert first[0].new_count == 1
    assert duplicate[0].status == "skipped"
    assert len(notifications) == 1
    assert notifications[0].workspace_id == workspace.workspace_id
    assert notifications[0].plan_id == plan.plan_id


def test_disabled_monitor_never_runs(tmp_path) -> None:
    core, _, _ = configured_core(tmp_path, enabled=False)

    results = LocalMonitorRunner(core.database).run_due(
        now=NOW,
        search=lambda _workspace, _plan: (_ for _ in ()).throw(
            AssertionError("disabled plan executed")
        ),
    )

    assert results == []


def test_failed_run_can_retry_without_marking_jobs_seen(tmp_path) -> None:
    core, _, _ = configured_core(tmp_path)
    runner = LocalMonitorRunner(core.database)

    def search(workspace_id, plan_id):
        return core.match_jobs(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )

    failed = runner.run_due(
        now=NOW,
        search=search,
        notify=lambda _summary: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    retried = runner.run_due(now=NOW, search=search)

    assert failed[0].status == "failed"
    assert retried[0].status == "success"
    assert retried[0].new_count == 1
    with core.database.connect() as connection:
        run = connection.execute("SELECT attempt, status FROM monitor_runs").fetchone()
    assert (run["attempt"], run["status"]) == (2, "success")


def test_missed_intervals_run_only_the_latest_slot(tmp_path) -> None:
    core, _, _ = configured_core(tmp_path)
    runner = LocalMonitorRunner(core.database)

    result = runner.run_due(
        now=NOW + timedelta(days=5, hours=2),
        search=lambda _workspace, _plan: (),
    )[0]

    assert result.status == "success"
    assert result.scheduled_for == datetime(2026, 8, 2, tzinfo=UTC)


def test_monitor_discovers_new_source_jobs_before_matching(tmp_path) -> None:
    class GrowingTransport:
        def __init__(self) -> None:
            self.jobs = [
                {
                    "id": "1",
                    "title": "AI应用工程师",
                    "content": "Python RAG",
                    "absolute_url": "https://example.com/jobs/1",
                }
            ]

        def get(self, _url: str) -> bytes:
            return json.dumps({"jobs": self.jobs}).encode()

    transport = GrowingTransport()
    core = JobFindsMeCore(tmp_path / "monitor.db")
    core.discovery = JobDiscoveryService(core.job_imports, transport=transport)
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="greenhouse",
                source_name="企业招聘官网",
                board_token="example",
            ),
        ),
    )
    core.configure_monitor(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        enabled=True,
        interval_hours=24,
    )
    runner = LocalMonitorRunner(core.database)

    def search(workspace_id, plan_id):
        return core.search_jobs(
            workspace_id=workspace_id,
            plan_id=plan_id,
        )

    first = runner.run_due(now=NOW, search=search)
    transport.jobs.append(
        {
            "id": "2",
            "title": "大模型应用工程师",
            "content": "Python Agent",
            "absolute_url": "https://example.com/jobs/2",
        }
    )
    second = runner.run_due(now=NOW + timedelta(days=1), search=search)

    assert first[0].new_count == 1
    assert second[0].new_count == 1
