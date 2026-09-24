from __future__ import annotations

import stat
from pathlib import Path

import pytest

from jobfindsme.profiles.models import FactStatus, FactType, ResumeImportMode
from jobfindsme.profiles.service import (
    ProfileError,
    ProfileNotFoundError,
    ResumeProfileService,
)
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService

RESUME = """# Skills
Python, FastAPI, RAG, Docker

# Projects
- Built jobfindsme with MCP and SQLite
"""


def make_service(tmp_path: Path):
    database = Database(tmp_path / "data" / "jobfindsme.db")
    database.migrate()
    workspaces = WorkspaceService(database)
    service = ResumeProfileService(database, data_root=tmp_path / "private")
    return database, workspaces, service


def write_resume(tmp_path: Path) -> Path:
    source = tmp_path / "resume.md"
    source.write_text(RESUME, encoding="utf-8")
    return source


@pytest.mark.parametrize(
    ("mode", "has_source", "has_managed"),
    [
        (ResumeImportMode.REFERENCE, True, False),
        (ResumeImportMode.MANAGED, False, True),
        (ResumeImportMode.FORGET_SOURCE, False, False),
    ],
)
def test_all_import_modes_apply_their_retention_policy(
    tmp_path: Path,
    mode: ResumeImportMode,
    has_source: bool,
    has_managed: bool,
) -> None:
    _, workspaces, service = make_service(tmp_path)
    workspace = workspaces.create()
    source = write_resume(tmp_path)

    profile = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
        mode=mode,
    )
    document = service.load_document(
        workspace_id=workspace.workspace_id,
        document_id=profile.document_id,
    )

    assert (document.source_path is not None) is has_source
    assert (document.managed_path is not None) is has_managed
    assert source.exists()
    if document.managed_path:
        managed = Path(document.managed_path)
        assert managed.read_text(encoding="utf-8") == RESUME
        assert stat.S_IMODE(managed.stat().st_mode) == 0o600


def test_database_never_stores_complete_resume_text(tmp_path: Path) -> None:
    database, workspaces, service = make_service(tmp_path)
    workspace = workspaces.create()
    profile = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=write_resume(tmp_path),
    )

    with database.connect() as connection:
        source_row = connection.execute(
            "SELECT * FROM source_documents WHERE document_id = ?",
            (profile.document_id,),
        ).fetchone()
        fact_rows = connection.execute(
            "SELECT * FROM profile_facts WHERE profile_id = ?",
            (profile.profile_id,),
        ).fetchall()

    assert RESUME not in tuple(source_row)
    assert all(RESUME not in tuple(row) for row in fact_rows)


def test_only_confirmed_facts_enter_adapter_summary(tmp_path: Path) -> None:
    _, workspaces, service = make_service(tmp_path)
    workspace = workspaces.create()
    profile = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=write_resume(tmp_path),
    )
    accepted = profile.facts[:2]

    with pytest.raises(ProfileError, match="not confirmed"):
        service.confirmed_summary(
            workspace_id=workspace.workspace_id,
            profile_id=profile.profile_id,
        )

    summary = service.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=profile.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in accepted],
        corrections={accepted[0].fact_id: "Python 3"},
    )

    assert len(summary.facts) == 2
    assert summary.facts[0].value == "Python 3"
    assert all(fact.status is FactStatus.CONFIRMED for fact in summary.facts)
    assert all(len(fact.evidence_snippet) <= 500 for fact in summary.facts)


def test_two_education_entries_can_both_be_confirmed(tmp_path: Path) -> None:
    _, workspaces, service = make_service(tmp_path)
    workspace = workspaces.create()
    source = tmp_path / "two-educations.md"
    source.write_text("教育经历\n2020.09-2024.06 示例大学 计算机科学 本科\n"
                      "2024.09-2026.06 示例研究院 人工智能 硕士\n", encoding="utf-8")
    profile = service.import_resume(workspace_id=workspace.workspace_id, source_path=source)
    education = [fact for fact in profile.facts if fact.fact_type is FactType.EDUCATION]
    assert len(education) == 2
    assert education[0].value.startswith("2020.09-2024.06")
    assert education[1].value.startswith("2024.09-2026.06")
    confirmed = service.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=profile.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in education],
    )
    assert [fact.value for fact in confirmed.facts] == [fact.value for fact in education]


def test_profile_is_isolated_by_workspace(tmp_path: Path) -> None:
    _, workspaces, service = make_service(tmp_path)
    owner = workspaces.create("owner")
    stranger = workspaces.create("stranger")
    profile = service.import_resume(
        workspace_id=owner.workspace_id,
        source_path=write_resume(tmp_path),
    )

    with pytest.raises(ProfileNotFoundError):
        service.load_review(
            workspace_id=stranger.workspace_id,
            profile_id=profile.profile_id,
        )


def test_same_resume_import_is_idempotent(tmp_path: Path) -> None:
    _, workspaces, service = make_service(tmp_path)
    workspace = workspaces.create()
    source = write_resume(tmp_path)

    first = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
    )
    second = service.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
    )

    assert first == second
