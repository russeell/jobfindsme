from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfReader

from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.resume_editor import ResumeEditorError, ResumeEditorService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def _confirmed_resume(tmp_path: Path):
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    profiles = ResumeProfileService(database)
    source = tmp_path / "resume.md"
    source.write_text(
        "# Skills\nPython、FastAPI、SQLite\n# Projects\n"
        "本地求职工具，负责确定性检索与隐私边界",
        encoding="utf-8",
    )
    draft = profiles.import_resume(
        workspace_id=workspace.workspace_id, source_path=source
    )
    profiles.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=draft.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in draft.facts],
    )
    return database, workspace, profiles


def test_structured_edit_conflict_and_restore_create_audited_versions(tmp_path) -> None:
    database, workspace, profiles = _confirmed_resume(tmp_path)
    editor = ResumeEditorService(database)
    first = profiles.current_version(workspace_id=workspace.workspace_id)
    assert first is not None
    edited = editor.save_edit(
        workspace_id=workspace.workspace_id,
        base_version_id=first.version_id,
        content={**first.content, "skills": ["Python", "FastAPI"]},
    )
    assert edited.version_number == 2
    assert edited.parent_version_id == first.version_id

    with pytest.raises(ResumeEditorError, match="conflict"):
        editor.save_edit(
            workspace_id=workspace.workspace_id,
            base_version_id=first.version_id,
            content=first.content,
        )

    restored = editor.restore_version(
        workspace_id=workspace.workspace_id, version_id=first.version_id
    )
    assert restored.version_number == 3
    assert restored.parent_version_id == edited.version_id
    assert restored.content == first.content
    assert [
        item.is_current
        for item in editor.list_versions(workspace_id=workspace.workspace_id)
    ] == [True, False, False]


def test_representative_chinese_resume_exports_pdf_docx_and_markdown(tmp_path) -> None:
    database, workspace, profiles = _confirmed_resume(tmp_path)
    editor = ResumeEditorService(database)
    current = profiles.current_version(workspace_id=workspace.workspace_id)
    assert current is not None
    projects = [
        f"项目 {index}：实现本地优先的求职工作流，"
        f"保留事实依据与隐私边界；验证条目 {index}。"
        for index in range(1, 34)
    ]
    projects.append("分页末尾校验：中文内容完整保留。")
    version = editor.save_edit(
        workspace_id=workspace.workspace_id,
        base_version_id=current.version_id,
        content={
            "basic_information": ["张三｜上海｜zhangsan@example.com"],
            "education": ["示例大学｜计算机科学｜本科"],
            "experience": ["示例公司｜应用工程师｜2023–至今"],
            "projects": projects,
            "skills": ["Python、FastAPI、SQLite、React"],
        },
    )

    pdf = editor.export(
        workspace_id=workspace.workspace_id,
        version_id=version.version_id,
        destination=tmp_path / "resume.pdf",
        format="pdf",
        template="classic",
    )
    docx = editor.export(
        workspace_id=workspace.workspace_id,
        version_id=version.version_id,
        destination=tmp_path / "resume.docx",
        format="docx",
        template="compact",
    )
    markdown = editor.export(
        workspace_id=workspace.workspace_id,
        version_id=version.version_id,
        destination=tmp_path / "resume.md",
        format="md",
        template="classic",
    )

    reader = PdfReader(pdf.path)
    assert 2 <= len(reader.pages) <= 4
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "分页末尾校验" in pdf_text
    assert all((page.extract_text() or "").strip() for page in reader.pages)
    document_text = "\n".join(p.text for p in Document(docx.path).paragraphs)
    assert "中文内容完整保留" in document_text
    assert "分页末尾校验" in markdown.path.read_text(encoding="utf-8")
    assert pdf.path.stat().st_mode & 0o077 == 0
    assert docx.path.stat().st_mode & 0o077 == 0
    assert markdown.path.stat().st_mode & 0o077 == 0
