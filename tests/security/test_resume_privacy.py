import sqlite3

import pytest

from jobfindsme.profiles.models import ResumeImportMode
from jobfindsme.profiles.service import ProfileError, ResumeProfileService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def test_unknown_workspace_cannot_import_resume(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    source = tmp_path / "resume.txt"
    source.write_text("Python RAG", encoding="utf-8")

    with pytest.raises(sqlite3.IntegrityError):
        ResumeProfileService(database).import_resume(
            workspace_id="missing",
            source_path=source,
        )


def test_confirmation_rejects_unknown_or_unaccepted_corrections(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    source = tmp_path / "resume.txt"
    source.write_text("Python RAG", encoding="utf-8")
    service = ResumeProfileService(database)
    profile = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
        mode=ResumeImportMode.FORGET_SOURCE,
    )

    with pytest.raises(ProfileError):
        service.confirm_profile(
            workspace_id=workspace.workspace_id,
            profile_id=profile.profile_id,
            accepted_fact_ids=[],
        )
    with pytest.raises(ProfileError):
        service.confirm_profile(
            workspace_id=workspace.workspace_id,
            profile_id=profile.profile_id,
            accepted_fact_ids=[profile.facts[0].fact_id],
            corrections={"unknown": "value"},
        )
