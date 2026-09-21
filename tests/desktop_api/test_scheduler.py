from datetime import UTC, datetime, timedelta

from jobfindsme.desktop_jobs import DesktopJobService
from jobfindsme.importing.repository import JobRepository
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.scheduler import LocalScheduler, TaskRunResult
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def setup_scheduler(tmp_path, now):
    database = Database(tmp_path / "scheduler.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    profiles = ResumeProfileService(database)
    path = tmp_path / "resume.md"
    path.write_text("# Skills\nPython", encoding="utf-8")
    draft = profiles.import_resume(
        workspace_id=workspace.workspace_id, source_path=path
    )
    profiles.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=draft.profile_id,
        accepted_fact_ids=[item.fact_id for item in draft.facts],
    )
    resume = profiles.current_version(workspace_id=workspace.workspace_id)
    rule = DesktopJobService(database, JobRepository(database)).ensure_rule_version(
        workspace.workspace_id
    )
    scheduler = LocalScheduler(database, clock=lambda: now[0])
    return database, workspace, resume, rule, scheduler


def test_scheduler_deduplicates_same_slot_and_collapses_missed_runs(tmp_path):
    now = [datetime(2026, 9, 18, 0, 0, tzinfo=UTC)]
    database, workspace, resume, rule, scheduler = setup_scheduler(tmp_path, now)
    task = scheduler.create_task(
        workspace_id=workspace.workspace_id,
        name="AI 岗位",
        intent="AI 应用工程师",
        source_ids=["liepin"],
        filters={"cities": ["上海"]},
        resume_version_id=resume.version_id,
        rule_version_id=rule,
        frequency="interval",
        timezone="Asia/Shanghai",
        interval_minutes=60,
        catch_up_policy="once",
    )
    now[0] += timedelta(hours=5)
    calls = []

    def runner(value):
        calls.append(value["task_id"])
        return TaskRunResult(
            status="success",
            new_count=2,
            result_fingerprint="same-results",
        )

    first = scheduler.run_due(runner)
    second = scheduler.run_due(runner)
    assert len(first) == 1
    assert second == []
    assert calls == [task["task_id"]]
    next_run = datetime.fromisoformat(
        scheduler.get_task(task["task_id"])["next_run_at"]
    )
    assert next_run > now[0]
    with database.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM desktop_task_runs").fetchone()[0]
            == 1
        )


def test_scheduler_pause_resume_timezone_failure_and_notification_dedupe(tmp_path):
    now = [datetime(2026, 9, 18, 0, 0, tzinfo=UTC)]
    _database, workspace, resume, rule, scheduler = setup_scheduler(tmp_path, now)
    task = scheduler.create_task(
        workspace_id=workspace.workspace_id,
        name="每日岗位",
        intent="Python",
        source_ids=["liepin"],
        filters={},
        resume_version_id=resume.version_id,
        rule_version_id=rule,
        frequency="daily",
        timezone="Asia/Shanghai",
        local_time="09:00",
    )
    assert task["next_run_at"].startswith("2026-09-18T01:00:00")
    scheduler.set_paused(task_id=task["task_id"], paused=True)
    now[0] = datetime(2026, 9, 19, 2, 0, tzinfo=UTC)
    assert scheduler.run_due(lambda _: TaskRunResult(status="success")) == []
    resumed = scheduler.set_paused(task_id=task["task_id"], paused=False)
    assert resumed["status"] == "active"
    now[0] = datetime.fromisoformat(resumed["next_run_at"]) + timedelta(minutes=1)

    def failed(_task):
        return TaskRunResult(status="login_required", error="猎聘登录失效")

    assert len(scheduler.run_due(failed)) == 1
    first_notifications = scheduler.pending_notifications()
    assert len(first_notifications) == 1
    # Force another slot with the same actionable failure; keep one notification.
    with scheduler.database.connect() as connection:
        connection.execute(
            "UPDATE desktop_scheduled_tasks SET next_run_at = ? WHERE task_id = ?",
            ((now[0] - timedelta(seconds=1)).isoformat(), task["task_id"]),
        )
    assert len(scheduler.run_due(failed)) == 1
    assert len(scheduler.pending_notifications()) == 1


def test_scheduler_recovers_stale_running_after_crash_and_keeps_future_runs(tmp_path):
    now = [datetime(2026, 9, 18, 0, 0, tzinfo=UTC)]
    database, workspace, resume, rule, scheduler = setup_scheduler(tmp_path, now)
    task = scheduler.create_task(
        workspace_id=workspace.workspace_id,
        name="断电恢复",
        intent="Python",
        source_ids=["liepin"],
        filters={},
        resume_version_id=resume.version_id,
        rule_version_id=rule,
        frequency="interval",
        timezone="Asia/Shanghai",
        interval_minutes=60,
    )
    due = task["next_run_at"]
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO desktop_task_runs (
                run_id, task_id, scheduled_for, status, started_at
            ) VALUES ('stale-run', ?, ?, 'running', ?)
            """,
            (
                task["task_id"],
                due,
                (datetime.fromisoformat(due) - timedelta(minutes=20)).isoformat(),
            ),
        )
        connection.execute(
            "UPDATE desktop_scheduled_tasks SET next_run_at = ? WHERE task_id = ?",
            (
                (datetime.fromisoformat(due) + timedelta(hours=1)).isoformat(),
                task["task_id"],
            ),
        )

    now[0] = datetime.fromisoformat(due) + timedelta(minutes=1)
    assert scheduler.run_due(lambda _: TaskRunResult(status="success")) == []
    with database.connect() as connection:
        recovered = connection.execute(
            "SELECT status, finished_at, error FROM desktop_task_runs "
            "WHERE run_id = 'stale-run'"
        ).fetchone()
    assert recovered["status"] == "failed"
    assert recovered["finished_at"]
    assert "异常退出或断电" in recovered["error"]
    assert len(scheduler.pending_notifications()) == 1

    now[0] = datetime.fromisoformat(due) + timedelta(hours=1, minutes=1)
    runs = scheduler.run_due(lambda _: TaskRunResult(status="success"))
    assert len(runs) == 1


def test_legacy_task_source_and_filter_snapshot_survives_new_preferences(tmp_path):
    now = [datetime(2026, 9, 18, 0, 0, tzinfo=UTC)]
    database, workspace, resume, rule, scheduler = setup_scheduler(tmp_path, now)
    frozen = {"unknown_policy": "exclude", "salary_mode": "contained"}
    task = scheduler.create_task(
        workspace_id=workspace.workspace_id,
        name="旧偏好快照",
        intent="Python",
        source_ids=["liepin"],
        filters=frozen,
        resume_version_id=resume.version_id,
        rule_version_id=rule,
        frequency="interval",
        timezone="Asia/Shanghai",
        interval_minutes=60,
    )
    now[0] = datetime.fromisoformat(task["next_run_at"]) + timedelta(seconds=1)
    received = []

    def run(value):
        received.append(value)
        return TaskRunResult(status="success")

    LocalScheduler(database, clock=lambda: now[0]).run_due(run)
    assert received[0]["source_ids"] == ["liepin"]
    assert received[0]["filters"] == frozen
    assert scheduler.get_task(task["task_id"])["filters"] == frozen
