from __future__ import annotations

from pathlib import Path

import pytest

from jobfindsme.app import jobfindsmecore
from jobfindsme.profiles.models import ResumeImportMode


def test_delete_requires_matching_single_use_confirmation_token(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("private")
    preview = core.preview_delete(
        workspace_id=workspace.workspace_id,
        scope="workspace",
    )
    assert preview.confirmation_token.startswith("del_")

    with pytest.raises(PermissionError):
        core.confirm_delete(
            workspace_id=workspace.workspace_id,
            scope="workspace",
            confirmation_token="wrong-token",
        )

    result = core.confirm_delete(
        workspace_id=workspace.workspace_id,
        scope="workspace",
        confirmation_token=preview.confirmation_token,
    )

    assert result.deleted is True
    assert core.list_workspaces() == []
    with core.database.connect() as connection:
        audit = connection.execute(
            "SELECT workspace_hash, scope FROM deletion_audit"
        ).fetchone()
        tokens = connection.execute("SELECT count(*) FROM deletion_tokens").fetchone()[
            0
        ]
    assert workspace.workspace_id not in audit["workspace_hash"]
    assert audit["scope"] == "workspace"
    assert tokens == 0


def test_delete_confirmation_survives_mcp_process_restart(tmp_path) -> None:
    database_path = tmp_path / "jobfindsme.db"
    first_process = jobfindsmecore(database_path)
    workspace = first_process.create_workspace("restart-safe")
    preview = first_process.preview_delete(
        workspace_id=workspace.workspace_id,
        scope="workspace",
    )

    second_process = jobfindsmecore(database_path)
    result = second_process.confirm_delete(
        workspace_id=workspace.workspace_id,
        scope="workspace",
        confirmation_token=preview.confirmation_token,
    )
    assert result.deleted is True


def test_export_contains_structured_data_but_no_complete_resume(tmp_path) -> None:
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG\n项目：求职助手", encoding="utf-8")
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("private")
    core.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=resume,
    )

    exported = core.export_local_data(workspace.workspace_id)

    assert exported["profile_facts"]
    assert "技能：Python、RAG\n项目：求职助手" not in str(exported)


def test_profile_deletion_removes_managed_resume_copy(tmp_path) -> None:
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")
    core = jobfindsmecore(tmp_path / "data" / "jobfindsme.db")
    workspace = core.create_workspace("private")
    profile = core.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=resume,
        mode=ResumeImportMode.MANAGED,
    )
    document = core.profiles.load_document(
        workspace_id=workspace.workspace_id,
        document_id=profile.document_id,
    )
    managed_path = document.managed_path
    assert managed_path is not None
    assert Path(managed_path).exists()

    preview = core.preview_delete(
        workspace_id=workspace.workspace_id,
        scope="profile",
    )
    core.confirm_delete(
        workspace_id=workspace.workspace_id,
        scope="profile",
        confirmation_token=preview.confirmation_token,
    )

    assert not Path(managed_path).exists()


def test_preview_counts_are_scope_aware(tmp_path) -> None:
    from jobfindsme.importing.parsers import parse_json

    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("private")
    ws = workspace.workspace_id
    core.job_imports.import_records(
        ws,
        parse_json(
            '[{"id":"j1","title":"AI应用工程师","company":"示例",'
            '"location":"上海","description":"Python RAG 25-40K",'
            '"url":"https://example.com/j1"}]',
            source_name="企业官网",
        ),
    )

    jobs_preview = core.preview_delete(workspace_id=ws, scope="jobs")
    profile_preview = core.preview_delete(workspace_id=ws, scope="profile")
    workspace_preview = core.preview_delete(workspace_id=ws, scope="workspace")

    assert jobs_preview.record_counts == {"jobs": 1}
    assert profile_preview.record_counts == {"profiles": 0}
    assert workspace_preview.record_counts["jobs"] == 1
