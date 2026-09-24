from pathlib import Path

from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def test_confirmation_creates_current_version_without_copying_source_text(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    service = ResumeProfileService(database)
    source = tmp_path / "resume.md"
    source.write_text(
        "# Skills\nPython RAG\n# Projects\nBuilt a local search tool",
        encoding="utf-8",
    )

    draft = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
    )
    service.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=draft.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in draft.facts],
    )

    version = service.current_version(workspace_id=workspace.workspace_id)
    assert version is not None
    assert version.source_document_id == draft.document_id
    assert version.version_number == 1
    assert version.content["skills"]
    with database.connect() as connection:
        row = connection.execute(
            "SELECT content_json FROM resume_versions WHERE version_id = ?",
            (version.version_id,),
        ).fetchone()
    assert source.read_text(encoding="utf-8") not in row["content_json"]


def test_new_confirmation_archives_previous_current_version(tmp_path: Path) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    service = ResumeProfileService(database)

    for index, skill in enumerate(("Python", "Docker"), start=1):
        source = tmp_path / f"resume-{index}.txt"
        source.write_text(skill, encoding="utf-8")
        draft = service.import_resume(
            workspace_id=workspace.workspace_id,
            source_path=source,
        )
        service.confirm_profile(
            workspace_id=workspace.workspace_id,
            profile_id=draft.profile_id,
            accepted_fact_ids=[fact.fact_id for fact in draft.facts],
        )

    versions = service.list_versions(workspace_id=workspace.workspace_id)
    assert [version.version_number for version in versions] == [2, 1]
    assert [version.is_current for version in versions] == [True, False]
    assert versions[0].parent_version_id == versions[1].version_id
