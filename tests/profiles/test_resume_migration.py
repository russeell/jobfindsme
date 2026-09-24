from pathlib import Path

from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def test_resume_and_model_migrations_preserve_legacy_profile_rows(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "legacy.db")
    database.migrate()
    workspace = WorkspaceService(database).create("legacy")
    source = tmp_path / "resume.txt"
    source.write_text("Python RAG", encoding="utf-8")
    profile = ResumeProfileService(database).import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
    )

    with database.connect() as connection:
        connection.execute("DROP TABLE resume_patches")
        connection.execute("DROP TABLE resume_edit_messages")
        connection.execute("DROP TABLE resume_edit_sessions")
        connection.execute("DROP TABLE active_resume_imports")
        connection.execute("DROP TABLE model_test_runs")
        connection.execute("DROP TABLE resume_versions")
        connection.execute("DROP TABLE model_connections")
        connection.execute(
            "DELETE FROM schema_migrations WHERE version IN (?, ?, ?, ?)",
            (
                "0014_resume_versions",
                "0015_model_connections",
                "0016_stage_b_review_fixes",
                "0017_resume_edit_sessions",
            ),
        )

    database.migrate()

    restored = ResumeProfileService(database).load_review(
        workspace_id=workspace.workspace_id,
        profile_id=profile.profile_id,
    )
    assert restored.facts == profile.facts
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM resume_versions").fetchone()[0]
            == 0
        )
        assert (
            connection.execute("SELECT count(*) FROM model_connections").fetchone()[0]
            == 0
        )
