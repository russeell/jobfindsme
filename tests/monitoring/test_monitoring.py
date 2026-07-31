from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jobfindsme.core import jobfindsmecore
from jobfindsme.importing.parsers import parse_json
from jobfindsme.monitoring import LocalMonitorRunner

NOW = datetime(2026, 7, 28, 8, 30, tzinfo=UTC)


def configured_core(tmp_path, *, enabled: bool = True):
    core = jobfindsmecore(tmp_path / "monitor.db")
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


# ── v0.5.0: arbitrary schedule (schedule_cron) ────────────────────────────────


def test_monitor_runs_only_when_cron_matches(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "cron.db")
    workspace = core.create_workspace("cron")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )
    core.configure_monitor(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        enabled=True,
        schedule_cron="0 9 * * *",  # daily 09:00
    )
    runner = LocalMonitorRunner(core.database)
    runs: list[str] = []

    def search(workspace_id, plan_id):
        runs.append("searched")
        return ()

    # 08:59 — cron not matched
    before = runner.run_due(
        now=datetime(2026, 8, 1, 8, 59, tzinfo=UTC), search=search
    )[0]
    assert before.status == "skipped"
    assert "cron" in (before.reason or "")
    assert runs == []

    # 09:00 — cron matched, runs
    at = runner.run_due(
        now=datetime(2026, 8, 1, 9, 0, tzinfo=UTC), search=search
    )[0]
    assert at.status == "success"
    assert runs == ["searched"]


def test_monitor_cron_supports_lists_steps_and_ranges() -> None:
    from jobfindsme.monitoring.service import _cron_matches

    now = datetime(2026, 8, 3, 10, 15, tzinfo=UTC)  # Monday 10:15
    assert _cron_matches("15 10 * * 1", now)  # Mondays 10:15
    assert not _cron_matches("15 10 * * 2", now)  # Tuesdays — no
    assert _cron_matches("*/15 * * * *", now)  # every 15 min
    assert _cron_matches("10-20 9-11 * * *", now)  # ranges
    assert _cron_matches("0 8 */2 * *", datetime(2026, 8, 2, 8, 0, tzinfo=UTC))  # even days
    assert not _cron_matches("0 8 */2 * *", datetime(2026, 8, 3, 8, 0, tzinfo=UTC))
    assert not _cron_matches("not a cron", now)  # invalid never fires


def test_configure_monitor_persists_schedule_cron(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "cron-persist.db")
    workspace = core.create_workspace("cron")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )

    config = core.configure_monitor(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        enabled=True,
        schedule_cron="0 20 * * 1",
    )

    assert config.schedule_cron == "0 20 * * 1"
    with core.database.connect() as connection:
        row = connection.execute(
            "SELECT schedule_cron FROM monitor_configs"
        ).fetchone()
    assert row["schedule_cron"] == "0 20 * * 1"
