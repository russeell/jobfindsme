from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from jobfindsme.contracts import JobMatch, StrictModel
from jobfindsme.storage import Database

SearchAction = Callable[[str, str], Sequence[JobMatch]]
NotifyAction = Callable[["MonitorSummary"], None]


class MonitorSummary(StrictModel):
    workspace_id: str
    plan_id: str
    scheduled_for: datetime
    matched: tuple[JobMatch, ...]
    new_matches: tuple[JobMatch, ...]


class MonitorRunResult(StrictModel):
    workspace_id: str
    plan_id: str
    scheduled_for: datetime
    status: str
    matched_count: int = 0
    new_count: int = 0
    reason: str | None = None


class LocalMonitorRunner:
    def __init__(
        self,
        database: Database,
        *,
        stale_run_after: timedelta = timedelta(minutes=30),
    ) -> None:
        self.database = database
        self.stale_run_after = stale_run_after

    def run_due(
        self,
        *,
        now: datetime,
        search: SearchAction,
        notify: NotifyAction | None = None,
    ) -> list[MonitorRunResult]:
        now = now.astimezone(UTC)
        with self.database.connect() as connection:
            configs = connection.execute(
                """
                SELECT workspace_id, plan_id, interval_hours, schedule_cron
                FROM monitor_configs WHERE enabled = 1
                ORDER BY workspace_id, plan_id
                """
            ).fetchall()
        return [
            self._run_config(
                workspace_id=row["workspace_id"],
                plan_id=row["plan_id"],
                interval_hours=row["interval_hours"],
                schedule_cron=row["schedule_cron"],
                now=now,
                search=search,
                notify=notify,
            )
            for row in configs
        ]

    def _run_config(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        interval_hours: int,
        schedule_cron: str | None,
        now: datetime,
        search: SearchAction,
        notify: NotifyAction | None,
    ) -> MonitorRunResult:
        if schedule_cron:
            # Arbitrary time/frequency: run only when the cron expression
            # matches the current minute.  An invalid expression never runs.
            if not _cron_matches(schedule_cron, now):
                return MonitorRunResult(
                    workspace_id=workspace_id,
                    plan_id=plan_id,
                    scheduled_for=now.replace(second=0, microsecond=0),
                    status="skipped",
                    reason="cron schedule not matched",
                )
            scheduled_for = now.replace(second=0, microsecond=0)
        else:
            scheduled_for = _latest_slot(now, interval_hours)
        if not self._claim(workspace_id, plan_id, scheduled_for, now):
            return MonitorRunResult(
                workspace_id=workspace_id,
                plan_id=plan_id,
                scheduled_for=scheduled_for,
                status="skipped",
                reason="slot already completed or currently running",
            )
        try:
            matches = tuple(search(workspace_id, plan_id))
            seen = self._seen_ids(workspace_id, plan_id)
            new_matches = tuple(item for item in matches if item.job.job_id not in seen)
            summary = MonitorSummary(
                workspace_id=workspace_id,
                plan_id=plan_id,
                scheduled_for=scheduled_for,
                matched=matches,
                new_matches=new_matches,
            )
            if notify is not None and new_matches:
                notify(summary)
            self._complete(summary, now)
        except Exception as error:
            self._fail(workspace_id, plan_id, scheduled_for, now, error)
            return MonitorRunResult(
                workspace_id=workspace_id,
                plan_id=plan_id,
                scheduled_for=scheduled_for,
                status="failed",
                reason=str(error),
            )
        return MonitorRunResult(
            workspace_id=workspace_id,
            plan_id=plan_id,
            scheduled_for=scheduled_for,
            status="success",
            matched_count=len(matches),
            new_count=len(new_matches),
        )

    def _claim(
        self,
        workspace_id: str,
        plan_id: str,
        scheduled_for: datetime,
        now: datetime,
    ) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT status, started_at, attempt FROM monitor_runs
                WHERE workspace_id = ? AND plan_id = ? AND scheduled_for = ?
                """,
                (workspace_id, plan_id, scheduled_for.isoformat()),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO monitor_runs (
                        workspace_id, plan_id, scheduled_for, status, started_at
                    ) VALUES (?, ?, ?, 'running', ?)
                    """,
                    (
                        workspace_id,
                        plan_id,
                        scheduled_for.isoformat(),
                        now.isoformat(),
                    ),
                )
                return True
            stale = datetime.fromisoformat(row["started_at"]) < (
                now - self.stale_run_after
            )
            if row["status"] == "success" or (row["status"] == "running" and not stale):
                return False
            connection.execute(
                """
                UPDATE monitor_runs SET
                    status = 'running', attempt = ?, started_at = ?,
                    finished_at = NULL, error = NULL
                WHERE workspace_id = ? AND plan_id = ? AND scheduled_for = ?
                """,
                (
                    row["attempt"] + 1,
                    now.isoformat(),
                    workspace_id,
                    plan_id,
                    scheduled_for.isoformat(),
                ),
            )
            return True

    def _seen_ids(self, workspace_id: str, plan_id: str) -> set[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT job_id FROM monitor_seen_jobs
                WHERE workspace_id = ? AND plan_id = ?
                """,
                (workspace_id, plan_id),
            ).fetchall()
        return {row["job_id"] for row in rows}

    def _complete(self, summary: MonitorSummary, now: datetime) -> None:
        with self.database.connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO monitor_seen_jobs (
                    workspace_id, plan_id, job_id, first_seen_at
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        summary.workspace_id,
                        summary.plan_id,
                        item.job.job_id,
                        now.isoformat(),
                    )
                    for item in summary.new_matches
                ],
            )
            connection.execute(
                """
                UPDATE monitor_runs SET
                    status = 'success', finished_at = ?,
                    matched_count = ?, new_count = ?
                WHERE workspace_id = ? AND plan_id = ? AND scheduled_for = ?
                """,
                (
                    now.isoformat(),
                    len(summary.matched),
                    len(summary.new_matches),
                    summary.workspace_id,
                    summary.plan_id,
                    summary.scheduled_for.isoformat(),
                ),
            )

    def _fail(
        self,
        workspace_id: str,
        plan_id: str,
        scheduled_for: datetime,
        now: datetime,
        error: Exception,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE monitor_runs SET
                    status = 'failed', finished_at = ?, error = ?
                WHERE workspace_id = ? AND plan_id = ? AND scheduled_for = ?
                """,
                (
                    now.isoformat(),
                    str(error)[:1000],
                    workspace_id,
                    plan_id,
                    scheduled_for.isoformat(),
                ),
            )


def _latest_slot(now: datetime, interval_hours: int) -> datetime:
    interval = interval_hours * 3600
    timestamp = now.timestamp()
    return datetime.fromtimestamp(timestamp - timestamp % interval, tz=UTC)


# ── 5-field cron matching (no external dependency) ────────────────────────────


def _cron_matches(expression: str, now: datetime) -> bool:
    """Match a 5-field cron (minute hour dom month dow) against *now*.

    Supports ``*``, lists (``1,15``), ranges (``9-17``) and steps
    (``*/15``, ``1-30/5``).  Day-of-week uses cron numbering where 0 and 7
    are Sunday.  Invalid expressions return False and never fire.
    """
    fields = expression.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    cron_dow = now.isoweekday() % 7  # cron: 0=Sunday; isoweekday 7=Sunday
    return (
        _field_matches(minute, now.minute)
        and _field_matches(hour, now.hour)
        and _field_matches(dom, now.day)
        and _field_matches(month, now.month)
        and _field_matches(dow, cron_dow)
    )


def _field_matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        if "/" in part:
            base, _, step_text = part.partition("/")
            try:
                step = int(step_text)
            except ValueError:
                continue
            if base == "*":
                if value % step == 0:
                    return True
            else:
                try:
                    start = int(base)
                except ValueError:
                    continue
                if value >= start and (value - start) % step == 0:
                    return True
        elif "-" in part:
            lo, _, hi = part.partition("-")
            try:
                if int(lo) <= value <= int(hi):
                    return True
            except ValueError:
                continue
        else:
            try:
                if int(part) == value:
                    return True
            except ValueError:
                continue
    return False
