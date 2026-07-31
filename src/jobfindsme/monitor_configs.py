from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import Field

from jobfindsme.contracts import StrictModel
from jobfindsme.storage import Database

Clock = Callable[[], datetime]


class MonitorConfig(StrictModel):
    workspace_id: str
    plan_id: str
    enabled: bool
    interval_hours: int = Field(ge=1, le=168)
    schedule_cron: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Optional 5-field cron for arbitrary time/frequency "
            "(e.g. '0 9 * * *' daily at 09:00, '0 20 * * 1' Mondays 20:00). "
            "Takes precedence over interval_hours."
        ),
    )
    notification_channel: str | None = None
    updated_at: datetime


class MonitorConfigService:
    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self.database = database
        self.clock = clock

    def configure(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        enabled: bool,
        interval_hours: int = 24,
        schedule_cron: str | None = None,
        notification_channel: str | None = None,
    ) -> MonitorConfig:
        config = MonitorConfig(
            workspace_id=workspace_id,
            plan_id=plan_id,
            enabled=enabled,
            interval_hours=interval_hours,
            schedule_cron=schedule_cron,
            notification_channel=notification_channel,
            updated_at=self.clock(),
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO monitor_configs (
                    workspace_id, plan_id, enabled, interval_hours,
                    schedule_cron, notification_channel, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, plan_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    interval_hours = excluded.interval_hours,
                    schedule_cron = excluded.schedule_cron,
                    notification_channel = excluded.notification_channel,
                    updated_at = excluded.updated_at
                """,
                (
                    config.workspace_id,
                    config.plan_id,
                    int(config.enabled),
                    config.interval_hours,
                    config.schedule_cron,
                    config.notification_channel,
                    config.updated_at.isoformat(),
                ),
            )
        return config
