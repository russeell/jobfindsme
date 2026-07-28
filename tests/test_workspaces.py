from datetime import UTC, datetime

import pytest

from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceNotFoundError, WorkspaceService


def test_workspace_create_get_and_list(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    service = WorkspaceService(
        database,
        clock=lambda: datetime(2026, 7, 28, tzinfo=UTC),
        id_factory=lambda: "workspace-1",
    )

    created = service.create("My AI Search")

    assert service.get(created.workspace_id) == created
    assert service.list() == [created]


def test_missing_workspace_is_rejected(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()

    with pytest.raises(WorkspaceNotFoundError):
        WorkspaceService(database).get("missing")
