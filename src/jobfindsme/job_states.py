from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from jobfindsme.contracts import JobState, JobStateKind
from jobfindsme.storage import Database

Clock = Callable[[], datetime]


class JobStateService:
    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self.database = database
        self.clock = clock

    def set(
        self,
        *,
        workspace_id: str,
        job_id: str,
        state: JobStateKind,
        note: str = "",
    ) -> JobState:
        value = JobState(
            workspace_id=workspace_id,
            job_id=job_id,
            state=state,
            note=note.strip(),
            updated_at=self.clock(),
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_states (
                    workspace_id, job_id, state, note, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, job_id) DO UPDATE SET
                    state = excluded.state,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (
                    value.workspace_id,
                    value.job_id,
                    value.state,
                    value.note,
                    value.updated_at.isoformat(),
                ),
            )
        return value

    def list(self, workspace_id: str) -> list[JobState]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM job_states
                WHERE workspace_id = ?
                ORDER BY updated_at DESC, job_id
                """,
                (workspace_id,),
            ).fetchall()
        return [
            JobState(
                workspace_id=row["workspace_id"],
                job_id=row["job_id"],
                state=row["state"],
                note=row["note"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]
