import io
from pathlib import Path

import pytest
from pypdf import PdfWriter

from jobfindsme.profiles.models import ResumeImportMode
from jobfindsme.profiles.service import (
    ProfileError,
    ProfileNotFoundError,
    ResumeProfileService,
)
from jobfindsme.resume_editor import ResumeEditorService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def setup(tmp_path):
    db = Database(tmp_path / "test.db")
    db.migrate()
    workspace = WorkspaceService(db).create().workspace_id
    return db, workspace, ResumeProfileService(db)


def test_original_bytes_survive_edit_restore_and_duplicate_import(tmp_path):
    db, workspace, service = setup(tmp_path)
    source = tmp_path / "fiction.md"
    original = b"# Projects\nSynthetic Python search project.\n# Skills\nPython"
    source.write_bytes(original)
    # Re-importing a previously reviewed document must preserve its edits and
    # create a source-first version without colliding with the legacy index.
    legacy = service.import_resume(
        workspace_id=workspace, source_path=source, mode=ResumeImportMode.MANAGED
    )
    service.confirm_profile(
        workspace_id=workspace,
        profile_id=legacy.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in legacy.facts],
    )
    profile = service.import_resume(
        workspace_id=workspace,
        source_path=source,
        mode=ResumeImportMode.MANAGED,
        index_original=True,
    )
    first = service.current_version(workspace_id=workspace)
    assert first.original_file
    assert service.active_draft_profile_id(workspace_id=workspace) is None
    source.unlink()  # The managed file must be sufficient.
    assert (
        service.original_document(
            workspace_id=workspace, document_id=profile.document_id
        )[1]
        == original
    )
    editor = ResumeEditorService(db)
    edited = editor.save_edit(
        workspace_id=workspace,
        base_version_id=first.version_id,
        content={**first.content, "skills": ["Python, SQL"]},
    )
    assert not edited.original_file
    other = tmp_path / "other.md"
    other.write_text("# Skills\nTypeScript")
    service.import_resume(
        workspace_id=workspace,
        source_path=other,
        mode=ResumeImportMode.MANAGED,
        index_original=True,
    )
    restored = editor.restore_version(
        workspace_id=workspace, version_id=first.version_id
    )
    assert restored.original_file
    assert restored.source_document_id == first.source_document_id
    assert (
        service.original_document(
            workspace_id=workspace, document_id=restored.source_document_id
        )[1]
        == original
    )
    source.write_bytes(original)
    service.import_resume(
        workspace_id=workspace,
        source_path=source,
        mode=ResumeImportMode.MANAGED,
        index_original=True,
    )
    assert (
        service.current_version(workspace_id=workspace).version_id
        == restored.version_id
    )
    with pytest.raises(ProfileNotFoundError):
        service.original_document(workspace_id="other", document_id=profile.document_id)
    document, _ = service.original_document(
        workspace_id=workspace, document_id=profile.document_id
    )
    Path(document.managed_path).write_bytes(b"changed")
    with pytest.raises(ProfileError, match="变化"):
        service.original_document(
            workspace_id=workspace, document_id=profile.document_id
        )

    service.import_resume(
        workspace_id=workspace,
        source_path=source,
        mode=ResumeImportMode.MANAGED,
        index_original=True,
    )
    assert (
        service.original_document(
            workspace_id=workspace, document_id=profile.document_id
        )[1]
        == original
    )
    assert (
        service.current_version(workspace_id=workspace).version_id
        == restored.version_id
    )


def test_valid_image_pdf_is_preserved_without_inventing_extracted_text(tmp_path):
    _, workspace, service = setup(tmp_path)
    pdf = PdfWriter()
    pdf.add_blank_page(width=500, height=700)
    stream = io.BytesIO()
    pdf.write(stream)
    source = tmp_path / "image.pdf"
    source.write_bytes(stream.getvalue())
    profile = service.import_resume(
        workspace_id=workspace,
        source_path=source,
        mode=ResumeImportMode.MANAGED,
        index_original=True,
    )
    version = service.current_version(workspace_id=workspace)
    assert version.original_file and not any(version.content.values())
    assert (
        service.original_document(
            workspace_id=workspace, document_id=profile.document_id
        )[1]
        == source.read_bytes()
    )
