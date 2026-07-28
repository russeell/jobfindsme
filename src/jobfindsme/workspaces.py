from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from jobfindsme.contracts import Workspace
from jobfindsme.storage import Database

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


class WorkspaceNotFoundError(LookupError):
    pass


class WorkspaceService:
    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = lambda: datetime.now(UTC),
        id_factory: IdFactory = lambda: f"ws_{uuid4().hex}",
    ) -> None:
        self.database = database
        self.clock = clock
        self.id_factory = id_factory

    def create(self, name: str = "My Job Search") -> Workspace:
        workspace = Workspace(
            workspace_id=self.id_factory(),
            name=name.strip(),
            created_at=self.clock(),
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (workspace_id, name, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    workspace.workspace_id,
                    workspace.name,
                    workspace.created_at.isoformat(),
                ),
            )
        return workspace

    def get(self, workspace_id: str) -> Workspace:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT workspace_id, name, created_at
                FROM workspaces
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            raise WorkspaceNotFoundError(workspace_id)
        return Workspace(
            workspace_id=row["workspace_id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list(self) -> list[Workspace]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT workspace_id, name, created_at
                FROM workspaces
                ORDER BY created_at, workspace_id
                """
            ).fetchall()
        return [
            Workspace(
                workspace_id=row["workspace_id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
