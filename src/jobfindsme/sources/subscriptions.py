from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from jobfindsme.contracts import (
    DiscoverySource,
    SourceHealth,
    SourceSubscription,
)
from jobfindsme.storage import Database


class SourceSubscriptionService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def replace(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        sources: Sequence[DiscoverySource],
    ) -> tuple[SourceSubscription, ...]:
        now = datetime.now(UTC)
        subscriptions = tuple(
            SourceSubscription(
                subscription_id=_subscription_id(
                    workspace_id, plan_id, source.kind, source.source_name
                ),
                workspace_id=workspace_id,
                plan_id=plan_id,
                source=source,
                enabled=True,
                health_status=SourceHealth.NEVER_CHECKED,
                created_at=now,
                updated_at=now,
            )
            for source in sources
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                DELETE FROM source_subscriptions
                WHERE workspace_id = ? AND plan_id = ?
                """,
                (workspace_id, plan_id),
            )
            connection.executemany(
                """
                INSERT INTO source_subscriptions (
                    subscription_id, workspace_id, plan_id, source_kind,
                    source_name, config_json, enabled, health_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.subscription_id,
                        item.workspace_id,
                        item.plan_id,
                        item.source.kind,
                        item.source.source_name,
                        item.source.model_dump_json(),
                        int(item.enabled),
                        item.health_status,
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                    )
                    for item in subscriptions
                ],
            )
        return subscriptions

    def list(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        enabled_only: bool = True,
    ) -> tuple[SourceSubscription, ...]:
        where = "AND enabled = 1" if enabled_only else ""
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM source_subscriptions
                WHERE workspace_id = ? AND plan_id = ? {where}
                ORDER BY created_at, subscription_id
                """,
                (workspace_id, plan_id),
            ).fetchall()
        return tuple(_from_row(row) for row in rows)

    def record_result(
        self,
        subscription: SourceSubscription,
        *,
        error: str | None,
        degraded: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        health = (
            SourceHealth.DEGRADED
            if degraded
            else SourceHealth.HEALTHY
            if error is None
            else SourceHealth.FAILED
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE source_subscriptions SET
                    health_status = ?, last_checked_at = ?, last_error = ?,
                    updated_at = ?
                WHERE subscription_id = ?
                """,
                (
                    health,
                    now.isoformat(),
                    error[:1000] if error else None,
                    now.isoformat(),
                    subscription.subscription_id,
                ),
            )


def _subscription_id(
    workspace_id: str,
    plan_id: str,
    kind: object,
    source_name: str,
) -> str:
    value = f"{workspace_id}\0{plan_id}\0{kind}\0{source_name.casefold()}"
    return f"source_{uuid5(NAMESPACE_URL, value).hex}"


def _from_row(row: object) -> SourceSubscription:
    return SourceSubscription(
        subscription_id=row["subscription_id"],
        workspace_id=row["workspace_id"],
        plan_id=row["plan_id"],
        source=DiscoverySource.model_validate(json.loads(row["config_json"])),
        enabled=bool(row["enabled"]),
        health_status=row["health_status"],
        last_checked_at=(
            datetime.fromisoformat(row["last_checked_at"])
            if row["last_checked_at"]
            else None
        ),
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
