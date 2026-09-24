"""Persistent in-process scheduler; it never claims OS wake-up support."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jobfindsme.storage import Database


class ScheduleError(ValueError):
    pass


@dataclass(frozen=True)
class TaskRunResult:
    status: str
    search_run_id: str | None = None
    new_count: int = 0
    changed_count: int = 0
    source_failures: tuple[str, ...] = ()
    result_snapshot: dict[str, str] | None = None
    result_fingerprint: str | None = None
    error: str | None = None


class LocalScheduler:
    def __init__(
        self,
        database: Database,
        *,
        clock: Callable[[], datetime] | None = None,
        running_lease: timedelta = timedelta(minutes=15),
    ) -> None:
        self.database = database
        self.clock = clock or (lambda: datetime.now(UTC))
        if running_lease <= timedelta(0):
            raise ValueError("running lease must be positive")
        self.running_lease = running_lease

    def create_task(
        self,
        *,
        workspace_id: str,
        name: str,
        intent: str,
        source_ids: list[str],
        filters: dict,
        resume_version_id: str,
        rule_version_id: str,
        frequency: str,
        timezone: str,
        local_time: str | None = None,
        weekday: int | None = None,
        interval_minutes: int | None = None,
        catch_up_policy: str = "once",
    ) -> dict:
        now = self._now()
        schedule = self._validate_schedule(
            frequency=frequency,
            timezone=timezone,
            local_time=local_time,
            weekday=weekday,
            interval_minutes=interval_minutes,
            catch_up_policy=catch_up_policy,
        )
        if not source_ids:
            raise ScheduleError("至少选择一个已允许的检索来源。")
        task_id = f"task_{uuid4().hex}"
        next_run = self._next_after(now, **schedule)
        with self.database.connect() as connection:
            resume = connection.execute(
                "SELECT 1 FROM resume_versions "
                "WHERE workspace_id = ? AND version_id = ?",
                (workspace_id, resume_version_id),
            ).fetchone()
            rule = connection.execute(
                "SELECT 1 FROM scoring_rule_versions "
                "WHERE workspace_id = ? AND rule_version_id = ?",
                (workspace_id, rule_version_id),
            ).fetchone()
            if resume is None or rule is None:
                raise ScheduleError(
                    "调度任务必须绑定当前工作空间的已确认简历和评分版本。"
                )
            connection.execute(
                """
                INSERT INTO desktop_scheduled_tasks (
                    task_id, workspace_id, name, intent, source_ids_json,
                    filter_snapshot_json, resume_version_id, rule_version_id,
                    frequency, local_time, weekday, interval_minutes, timezone,
                    catch_up_policy, status, next_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    task_id,
                    workspace_id,
                    name.strip(),
                    intent.strip(),
                    json.dumps(list(dict.fromkeys(source_ids)), ensure_ascii=False),
                    json.dumps(filters, ensure_ascii=False, sort_keys=True),
                    resume_version_id,
                    rule_version_id,
                    frequency,
                    local_time,
                    weekday,
                    interval_minutes,
                    timezone,
                    catch_up_policy,
                    next_run.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get_task(task_id)

    def list_tasks(self, *, workspace_id: str) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM desktop_scheduled_tasks WHERE workspace_id = ? "
                "ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        return [self._task(row) for row in rows]

    def get_task(self, task_id: str) -> dict:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM desktop_scheduled_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise LookupError(task_id)
        return self._task(row)

    def set_paused(self, *, task_id: str, paused: bool) -> dict:
        now = self._now()
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM desktop_scheduled_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise LookupError(task_id)
            next_run = row["next_run_at"]
            if not paused:
                schedule = self._schedule_from_row(row)
                next_run = self._next_after(now, **schedule).isoformat()
            connection.execute(
                "UPDATE desktop_scheduled_tasks "
                "SET status = ?, next_run_at = ?, updated_at = ? WHERE task_id = ?",
                ("paused" if paused else "active", next_run, now.isoformat(), task_id),
            )
        return self.get_task(task_id)

    def run_due(
        self, runner: Callable[[dict], TaskRunResult], *, now: datetime | None = None
    ) -> list[dict]:
        current = (now or self._now()).astimezone(UTC)
        self._recover_stale_runs(current)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM desktop_scheduled_tasks "
                "WHERE status = 'active' AND next_run_at <= ? "
                "ORDER BY next_run_at, task_id",
                (current.isoformat(),),
            ).fetchall()
        results = []
        for row in rows:
            result = self._run_one(row, runner, current)
            if result is not None:
                results.append(result)
        return results

    def list_due(self, *, now: datetime | None = None) -> list[dict]:
        current = (now or self._now()).astimezone(UTC)
        self._recover_stale_runs(current)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM desktop_scheduled_tasks "
                "WHERE status = 'active' AND next_run_at <= ? "
                "ORDER BY next_run_at, task_id",
                (current.isoformat(),),
            ).fetchall()
        return [self._task(row) for row in rows]

    def _recover_stale_runs(self, current: datetime) -> None:
        cutoff = (current - self.running_lease).isoformat()
        error = (
            "上次运行在应用异常退出或断电后未完成，已按运行租约标记失败；"
            "后续计划仍会继续。"
        )
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.run_id, r.task_id, t.*
                FROM desktop_task_runs r
                JOIN desktop_scheduled_tasks t ON t.task_id = r.task_id
                WHERE r.status = 'running' AND r.started_at <= ?
                ORDER BY r.started_at, r.run_id
                """,
                (cutoff,),
            ).fetchall()
            for row in rows:
                changed = connection.execute(
                    """
                    UPDATE desktop_task_runs
                    SET status = 'failed', finished_at = ?, error = ?
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (current.isoformat(), error, row["run_id"]),
                ).rowcount
                if not changed:
                    continue
                connection.execute(
                    "UPDATE desktop_scheduled_tasks SET last_error = ? "
                    "WHERE task_id = ?",
                    (error, row["task_id"]),
                )
                self._notifications(
                    connection,
                    self._task(row),
                    row["run_id"],
                    TaskRunResult(status="failed", error=error),
                    current,
                )

    def _run_one(self, row, runner, current: datetime) -> dict | None:
        task = self._task(row)
        original_due = datetime.fromisoformat(row["next_run_at"]).astimezone(UTC)
        schedule = self._schedule_from_row(row)
        next_run = original_due
        while next_run <= current:
            next_run = self._next_after(next_run, **schedule)
        if row["catch_up_policy"] == "skip" and original_due < current:
            with self.database.connect() as connection:
                connection.execute(
                    "UPDATE desktop_scheduled_tasks SET next_run_at = ?, "
                    "updated_at = ? WHERE task_id = ?",
                    (next_run.isoformat(), current.isoformat(), row["task_id"]),
                )
            return None
        run_id = f"task_run_{uuid4().hex}"
        with self.database.connect() as connection:
            running = connection.execute(
                "SELECT 1 FROM desktop_task_runs "
                "WHERE task_id = ? AND status = 'running'",
                (row["task_id"],),
            ).fetchone()
            if running is not None:
                return None
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO desktop_task_runs (
                    run_id, task_id, scheduled_for, status, started_at
                ) VALUES (?, ?, ?, 'running', ?)
                """,
                (run_id, row["task_id"], original_due.isoformat(), current.isoformat()),
            ).rowcount
            if not inserted:
                return None
            connection.execute(
                "UPDATE desktop_scheduled_tasks SET next_run_at = ?, "
                "updated_at = ? WHERE task_id = ?",
                (next_run.isoformat(), current.isoformat(), row["task_id"]),
            )
        try:
            outcome = runner(task)
        except Exception as error:
            outcome = TaskRunResult(status="failed", error=str(error))
        if outcome.status not in {"success", "partial", "failed", "login_required"}:
            outcome = TaskRunResult(
                status="failed", error="scheduler runner returned an invalid status"
            )
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE desktop_task_runs
                SET status = ?, finished_at = ?, search_run_id = ?,
                    new_count = ?, changed_count = ?, source_failures_json = ?,
                    result_snapshot_json = ?, result_fingerprint = ?,
                    error = ? WHERE run_id = ?
                """,
                (
                    outcome.status,
                    current.isoformat(),
                    outcome.search_run_id,
                    outcome.new_count,
                    outcome.changed_count,
                    json.dumps(outcome.source_failures, ensure_ascii=False),
                    json.dumps(outcome.result_snapshot or {}, sort_keys=True),
                    outcome.result_fingerprint,
                    outcome.error,
                    run_id,
                ),
            )
            connection.execute(
                "UPDATE desktop_scheduled_tasks SET last_error = ? WHERE task_id = ?",
                (
                    outcome.error
                    if outcome.status in {"failed", "login_required", "partial"}
                    else None,
                    row["task_id"],
                ),
            )
            self._notifications(connection, task, run_id, outcome, current)
        return {"run_id": run_id, "task_id": row["task_id"], **outcome.__dict__}

    def pending_notifications(self) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM desktop_task_notifications "
                "WHERE delivered_at IS NULL ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_notification_delivered(self, notification_id: str) -> None:
        with self.database.connect() as connection:
            changed = connection.execute(
                "UPDATE desktop_task_notifications SET delivered_at = ? "
                "WHERE notification_id = ?",
                (self._now().isoformat(), notification_id),
            ).rowcount
        if not changed:
            raise LookupError(notification_id)

    def legacy_status(self, *, workspace_id: str) -> dict:
        with self.database.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM monitor_configs WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()[0]
        return {
            "legacy_monitor_count": count,
            "migration_status": "requires_reconfiguration" if count else "none",
            "detail": (
                "旧 monitor 缺少简历/评分快照和时区，不自动启用；用户需在本页重新确认。"
            )
            if count
            else "没有待迁移的旧 monitor 配置。",
        }

    @staticmethod
    def _notifications(connection, task, run_id, outcome, now) -> None:
        events = []
        if outcome.new_count:
            events.append(
                (
                    "new_jobs",
                    f"新增 {outcome.new_count} 个岗位",
                    f"{outcome.result_fingerprint or run_id}:new:{outcome.new_count}",
                )
            )
        if outcome.changed_count:
            events.append(
                (
                    "changed_jobs",
                    f"有 {outcome.changed_count} 个岗位发生变化",
                    f"{outcome.result_fingerprint or run_id}:changed:"
                    f"{outcome.changed_count}",
                )
            )
        if outcome.status in {"failed", "login_required", "partial"}:
            message = outcome.error or "定时检索失败"
            events.append(("failure", message, f"failure:{message}"))
        for kind, body, raw_key in events:
            event_key = hashlib.sha256(raw_key.encode()).hexdigest()
            connection.execute(
                """
                INSERT OR IGNORE INTO desktop_task_notifications (
                    notification_id, task_id, run_id, event_key, kind,
                    title, body, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"notification_{uuid4().hex}",
                    task["task_id"],
                    run_id,
                    event_key,
                    kind,
                    task["name"],
                    body,
                    now.isoformat(),
                ),
            )

    def _validate_schedule(self, **values) -> dict:
        frequency = values["frequency"]
        try:
            ZoneInfo(values["timezone"])
        except ZoneInfoNotFoundError as error:
            raise ScheduleError("无效时区。") from error
        if frequency not in {"interval", "daily", "weekly"}:
            raise ScheduleError("频率必须是 interval、daily 或 weekly。")
        if values["catch_up_policy"] not in {"once", "skip"}:
            raise ScheduleError("补跑策略必须是 once 或 skip。")
        if frequency == "interval":
            minutes = values["interval_minutes"]
            if minutes is None or not 15 <= minutes <= 10080:
                raise ScheduleError("间隔时长必须在 15 分钟到 7 天之间。")
        else:
            if not re_time(values["local_time"]):
                raise ScheduleError("每日/每周调度需要 HH:MM 本地时间。")
            if frequency == "weekly" and values["weekday"] not in range(7):
                raise ScheduleError("每周调度需要 0-6 的星期值。")
        return values

    @staticmethod
    def _next_after(
        moment: datetime,
        *,
        frequency,
        timezone,
        local_time,
        weekday,
        interval_minutes,
        catch_up_policy,
    ) -> datetime:
        del catch_up_policy
        if frequency == "interval":
            return moment.astimezone(UTC) + timedelta(minutes=interval_minutes)
        zone = ZoneInfo(timezone)
        local = moment.astimezone(zone)
        hour, minute = (int(part) for part in local_time.split(":"))
        candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if frequency == "daily":
            if candidate <= local:
                candidate += timedelta(days=1)
        else:
            candidate += timedelta(days=(weekday - candidate.weekday()) % 7)
            if candidate <= local:
                candidate += timedelta(days=7)
        return candidate.astimezone(UTC)

    @staticmethod
    def _schedule_from_row(row) -> dict:
        return {
            key: row[key]
            for key in (
                "frequency",
                "timezone",
                "local_time",
                "weekday",
                "interval_minutes",
                "catch_up_policy",
            )
        }

    @staticmethod
    def _task(row) -> dict:
        value = dict(row)
        value["source_ids"] = json.loads(value.pop("source_ids_json"))
        value["filters"] = json.loads(value.pop("filter_snapshot_json"))
        return value

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            raise ScheduleError("调度时钟必须包含时区。")
        return value.astimezone(UTC)


def re_time(value: str | None) -> bool:
    if value is None:
        return False
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except (TypeError, ValueError):
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59 and len(value) == 5
