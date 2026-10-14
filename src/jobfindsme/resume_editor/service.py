from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from jobfindsme.profiles.models import ResumeVersion
from jobfindsme.profiles.text import normalize_resume_document, normalize_resume_text
from jobfindsme.resume_editor.document import (
    document_content,
    document_template,
    paragraphs,
    pdf_markup,
    reconcile_document,
    validate_document,
)
from jobfindsme.resume_editor.source_format import retained_document
from jobfindsme.storage import Database

ResumeTemplate = Literal["classic", "compact", "campus", "professional"]
ResumeFormat = Literal["pdf", "docx", "md"]
SECTION_ORDER = (
    "basic_information",
    "education",
    "experience",
    "projects",
    "skills",
)
SECTION_TITLES = {
    "basic_information": "基本信息",
    "education": "教育经历",
    "experience": "工作经历",
    "projects": "项目经历",
    "skills": "专业技能",
}


class ResumeEditorError(ValueError):
    pass


@dataclass(frozen=True)
class ResumeExport:
    path: Path
    format: ResumeFormat
    template: ResumeTemplate
    version_id: str


class ResumeEditorService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_versions(self, *, workspace_id: str) -> list[ResumeVersion]:
        self.database.migrate()
        with self.database.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM resume_versions WHERE workspace_id = ?
                AND hidden_at IS NULL
                ORDER BY version_number DESC""",
                (workspace_id,),
            ).fetchall()
            return [
                _version_from_row(
                    row,
                    retained_document(
                        connection, row, data_root=self.database.path.parent
                    ),
                )
                for row in rows
            ]

    def hide_version(self, *, workspace_id: str, version_id: str) -> None:
        """Remove a historical list entry while retaining immutable references."""
        self.database.migrate()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT is_current, hidden_at FROM resume_versions "
                "WHERE workspace_id=? AND version_id=?",
                (workspace_id, version_id),
            ).fetchone()
            if row is None:
                raise ResumeEditorError("resume version not found")
            if row["is_current"]:
                raise ResumeEditorError("current resume version cannot be hidden")
            if row["hidden_at"] is not None:
                return
            connection.execute(
                "UPDATE resume_versions SET hidden_at=? "
                "WHERE workspace_id=? AND version_id=? AND is_current=0",
                (datetime.now(UTC).isoformat(), workspace_id, version_id),
            )

    def get_version(self, *, workspace_id: str, version_id: str) -> ResumeVersion:
        self.database.migrate()
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM resume_versions
                WHERE workspace_id = ? AND version_id = ?""",
                (workspace_id, version_id),
            ).fetchone()
            if row is None:
                raise ResumeEditorError("resume version not found")
            rich = retained_document(
                connection, row, data_root=self.database.path.parent
            )
        return _version_from_row(row, rich)

    def save_edit(
        self,
        *,
        workspace_id: str,
        base_version_id: str,
        content: dict[str, list[str] | tuple[str, ...]],
        document: dict | None = None,
    ) -> ResumeVersion:
        normalized = _normalize_content(content)
        if document is not None:
            try:
                document = validate_document(document)
            except (ValueError, TypeError, AttributeError) as error:
                raise ResumeEditorError("invalid resume document") from error
            if document_content(document) != normalized:
                raise ResumeEditorError("resume document text does not match content")
        return self._create_from_base(
            workspace_id=workspace_id,
            base_version_id=base_version_id,
            content=normalized,
            document=document,
        )

    def restore_version(
        self,
        *,
        workspace_id: str,
        version_id: str,
    ) -> ResumeVersion:
        target = self.get_version(workspace_id=workspace_id, version_id=version_id)
        if not any(
            version.version_id == target.version_id
            for version in self.list_versions(workspace_id=workspace_id)
        ):
            raise ResumeEditorError("hidden resume version cannot be restored")
        with self.database.connect() as connection:
            current = connection.execute(
                """SELECT version_id FROM resume_versions
                WHERE workspace_id = ? AND is_current = 1""",
                (workspace_id,),
            ).fetchone()
        if current is None:
            with self.database.connect() as connection:
                return self._create_from_base_in_transaction(
                    connection=connection,
                    workspace_id=workspace_id,
                    base_version_id=target.version_id,
                    content=target.content,
                    document=reconcile_document(target.content, target.document),
                    restored=target,
                    allow_missing_current=True,
                )
        return self._create_from_base(
            workspace_id=workspace_id,
            base_version_id=current["version_id"],
            content=target.content,
            document=reconcile_document(target.content, target.document),
            restored=target,
        )

    def _create_from_base(
        self,
        *,
        workspace_id: str,
        base_version_id: str,
        content: dict[str, tuple[str, ...]],
        document: dict | None = None,
        restored: ResumeVersion | None = None,
    ) -> ResumeVersion:
        with self.database.connect() as connection:
            return self._create_from_base_in_transaction(
                connection=connection,
                workspace_id=workspace_id,
                base_version_id=base_version_id,
                content=content,
                document=document,
                restored=restored,
            )

    def _create_from_base_in_transaction(
        self,
        *,
        connection,
        workspace_id: str,
        base_version_id: str,
        content: dict[str, tuple[str, ...]],
        document: dict | None = None,
        restored: ResumeVersion | None = None,
        make_current: bool = True,
        allow_missing_current: bool = False,
    ) -> ResumeVersion:
        """Create a version on a caller-owned transaction.

        Prompt-session saves use this so advancing the current version and
        closing the edit session commit or roll back together.
        """
        now = datetime.now(UTC)
        version_id = f"resume_version_{uuid4().hex}"
        base = connection.execute(
            """SELECT * FROM resume_versions
            WHERE workspace_id = ? AND version_id = ?""",
            (workspace_id, base_version_id),
        ).fetchone()
        if base is None:
            raise ResumeEditorError("base resume version not found")
        current = connection.execute(
            """SELECT version_id FROM resume_versions
            WHERE workspace_id = ? AND is_current = 1""",
            (workspace_id,),
        ).fetchone()
        if make_current and (
            (current is None and not allow_missing_current)
            or (current is not None and current["version_id"] != base_version_id)
        ):
            raise ResumeEditorError(
                "resume version conflict: reload the current version before saving"
            )
        if document is None:
            document = reconcile_document(
                content,
                json.loads(base["document_json"])
                if base["document_json"]
                else retained_document(
                    connection, base, data_root=self.database.path.parent
                ),
            )
        next_number = connection.execute(
            """SELECT COALESCE(MAX(version_number), 0) + 1
            FROM resume_versions WHERE workspace_id = ?""",
            (workspace_id,),
        ).fetchone()[0]
        if make_current:
            connection.execute(
                "UPDATE resume_versions SET is_current = 0 WHERE workspace_id = ?",
                (workspace_id,),
            )
        connection.execute(
            """INSERT INTO resume_versions (
                version_id, workspace_id, profile_id, source_document_id,
                parent_version_id, version_number, content_json,
                is_current, created_at, document_json, original_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                workspace_id,
                restored.profile_id if restored else base["profile_id"],
                restored.source_document_id if restored else base["source_document_id"],
                base_version_id,
                next_number,
                json.dumps(content, ensure_ascii=False),
                int(make_current),
                now.isoformat(),
                json.dumps(document, ensure_ascii=False),
                int(restored.original_file) if restored else 0,
            ),
        )
        created = connection.execute(
            "SELECT * FROM resume_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        return _version_from_row(created)

    def export(
        self,
        *,
        workspace_id: str,
        version_id: str,
        destination: str | Path,
        format: ResumeFormat,
        template: ResumeTemplate | None = None,
    ) -> ResumeExport:
        if format not in {"pdf", "docx", "md"}:
            raise ResumeEditorError("unsupported export format")
        if template is not None and template not in {
            "classic",
            "compact",
            "campus",
            "professional",
        }:
            raise ResumeEditorError("unsupported resume template")
        version = self.get_version(workspace_id=workspace_id, version_id=version_id)
        template = template or document_template(version.document) or "professional"
        path = Path(destination).expanduser()
        if path.suffix.casefold() != f".{format}":
            raise ResumeEditorError(f"export path must end with .{format}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if format == "md":
            path.write_text(_markdown(version.content, template), encoding="utf-8")
        elif format == "docx":
            _write_docx(path, version.content, template, version.document)
        else:
            _write_pdf(path, version.content, template, version.document)
        os.chmod(path, 0o600)
        return ResumeExport(path, format, template, version.version_id)


def _normalize_content(
    content: dict[str, list[str] | tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    unknown = set(content) - set(SECTION_ORDER)
    if unknown:
        raise ResumeEditorError(f"unknown resume sections: {sorted(unknown)}")
    normalized: dict[str, tuple[str, ...]] = {}
    for section in SECTION_ORDER:
        values = content.get(section, ())
        if not isinstance(values, (list, tuple)):
            raise ResumeEditorError(f"resume section {section} must be a list")
        # Preserve the editor's line breaks and spacing exactly across versions.
        cleaned = tuple(str(value) for value in values)
        normalized[section] = cleaned
    if not any(value.strip() for values in normalized.values() for value in values):
        raise ResumeEditorError("resume content must not be empty")
    return normalized


def _template_sections(template: ResumeTemplate) -> tuple[str, ...]:
    if template == "campus":
        return ("basic_information", "education", "projects", "experience", "skills")
    if template in {"professional", "compact"}:
        return ("basic_information", "experience", "projects", "skills", "education")
    return SECTION_ORDER


def _markdown(content: dict[str, tuple[str, ...]], template: ResumeTemplate) -> str:
    lines = ["# 简历", ""]
    for section in _template_sections(template):
        values = content.get(section, ())
        if not any(value.strip() for value in values):
            continue
        lines.extend([f"## {SECTION_TITLES[section]}", ""])
        marker = "- " if template == "classic" else ""
        for value in values:
            lines.extend([f"{marker}{value}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _write_docx(
    path: Path,
    content: dict[str, tuple[str, ...]],
    template: ResumeTemplate,
    rich_document: dict | None = None,
) -> None:
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt, RGBColor
    except ImportError as error:
        raise ResumeEditorError(
            "DOCX export requires the python-docx dependency"
        ) from error
    rich = reconcile_document(content, rich_document)
    blocks = {s["attrs"]["section"]: s["content"] for s in rich["content"]}
    section_styles = {s["attrs"]["section"]: s["attrs"] for s in rich["content"]}
    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.45 if template == "compact" else 1.8)
    section.bottom_margin = section.top_margin
    section.left_margin = Cm(1.65 if template == "compact" else 2.0)
    section.right_margin = section.left_margin
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "PingFang SC")
    normal.font.size = Pt(9.5 if template == "compact" else 10.5)
    for name in _template_sections(template):
        values = content.get(name, ())
        if not any(value.strip() for value in values):
            continue
        style = section_styles[name]
        if not style.get("headingHidden"):
            heading = document.add_heading(SECTION_TITLES[name], level=1)
            heading.runs[0].font.color.rgb = RGBColor.from_string(
                style.get(
                    "headingColor", "#256396" if template == "campus" else "#30302e"
                )[1:]
            )
            if style.get("headingSize"):
                heading.runs[0].font.size = Pt(style["headingSize"])
        for block in blocks[name]:
            for prefix, node in paragraphs(block):
                p = document.add_paragraph()
                if template == "classic" and not prefix:
                    p.style = document.styles["List Bullet"]
                p.paragraph_format.space_after = Pt(2 if template == "compact" else 5)
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                align = node.get("attrs", {}).get("textAlign")
                if align:
                    p.alignment = {
                        "left": WD_ALIGN_PARAGRAPH.LEFT,
                        "center": WD_ALIGN_PARAGRAPH.CENTER,
                        "right": WD_ALIGN_PARAGRAPH.RIGHT,
                        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
                    }[align]
                if prefix:
                    p.add_run(prefix)
                for child in node.get("content", []):
                    run = p.add_run(
                        "\n" if child["type"] == "hardBreak" else child["text"]
                    )
                    marks = {m["type"] for m in child.get("marks", [])}
                    run.bold = "bold" in marks
                    run.italic = "italic" in marks
                    run.underline = "underline" in marks
                    run.font.strike = "strike" in marks
                    for mark in child.get("marks", []):
                        if mark["type"] == "textStyle":
                            attrs = mark.get("attrs", {})
                            if attrs.get("color"):
                                run.font.color.rgb = RGBColor.from_string(
                                    attrs["color"][1:]
                                )
                            if attrs.get("fontSize"):
                                run.font.size = Pt(attrs["fontSize"])
    document.save(path)


def _write_pdf(
    path: Path,
    content: dict[str, tuple[str, ...]],
    template: ResumeTemplate,
    rich_document: dict | None = None,
) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as error:
        raise ResumeEditorError(
            "PDF export requires the reportlab dependency"
        ) from error
    rich = reconcile_document(content, rich_document)
    blocks = {s["attrs"]["section"]: s["content"] for s in rich["content"]}
    section_styles = {s["attrs"]["section"]: s["attrs"] for s in rich["content"]}
    font_name = _register_cjk_font(pdfmetrics, TTFont)
    bold_font = font_name
    for candidate in (
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyhbd.ttc",
    ):
        if candidate.exists():
            try:
                pdfmetrics.registerFont(
                    TTFont("JobFindsMeCJKBold", str(candidate), subfontIndex=0)
                )
                bold_font = "JobFindsMeCJKBold"
                break
            except Exception:
                continue
    pdfmetrics.registerFontFamily(
        font_name,
        normal=font_name,
        bold=bold_font,
        italic=font_name,
        boldItalic=bold_font,
    )
    margin = (15 if template == "compact" else 19) * mm
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title="简历",
        author="JobFindsMe",
    )
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        "ResumeHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#256396" if template == "campus" else "#30302e"),
        spaceBefore=(2.5 if template == "compact" else 4) * mm,
        spaceAfter=2 * mm,
        borderWidth=0,
        borderPadding=0,
    )
    body = ParagraphStyle(
        "ResumeBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8.8 if template == "compact" else 9.8,
        leading=13 if template == "compact" else 15,
        textColor=colors.HexColor("#3f3f3c"),
        leftIndent=0 if template == "compact" else 3 * mm,
        spaceAfter=1.5 * mm if template == "compact" else 2.5 * mm,
        wordWrap="CJK",
    )
    story = []
    for name in _template_sections(template):
        values = content.get(name, ())
        if not any(value.strip() for value in values):
            continue
        style = section_styles[name]
        if not style.get("headingHidden"):
            section_heading = ParagraphStyle(
                f"Heading-{name}",
                parent=heading,
                textColor=colors.HexColor(
                    style.get("headingColor", heading.textColor.hexval())
                ),
                fontSize=style.get("headingSize", heading.fontSize),
                leading=max(heading.leading, style.get("headingSize", 0) * 1.4),
                fontName=bold_font,
            )
            story.extend(
                [Paragraph(SECTION_TITLES[name], section_heading), Spacer(1, 0.5 * mm)]
            )
        for block in blocks[name]:
            for prefix, node in paragraphs(block):
                if template == "classic" and not prefix:
                    prefix = "• "
                markup = _xml_escape(prefix) + "".join(
                    pdf_markup(c) for c in node.get("content", [])
                )
                largest = max(
                    (
                        m.get("attrs", {}).get("fontSize", body.fontSize)
                        for child in node.get("content", [])
                        for m in child.get("marks", [])
                        if m["type"] == "textStyle"
                    ),
                    default=body.fontSize,
                )
                paragraph_style = ParagraphStyle(
                    "StyledBody",
                    parent=body,
                    leading=max(body.leading, largest * 1.4),
                    alignment={"left": 0, "center": 1, "right": 2, "justify": 4}.get(
                        node.get("attrs", {}).get("textAlign"), 0
                    ),
                )
                story.append(Paragraph(markup or "<br/>", paragraph_style))
    document.build(story)


def _register_cjk_font(pdfmetrics, ttfont) -> str:
    import os

    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates = (
        windows_fonts / "msyh.ttc",
        windows_fonts / "simsun.ttc",
        windows_fonts / "msjh.ttc",
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for candidate in candidates:
        if candidate.exists():
            try:
                pdfmetrics.registerFont(
                    ttfont("JobFindsMeCJK", str(candidate), subfontIndex=0)
                )
                return "JobFindsMeCJK"
            except Exception:
                continue
    raise ResumeEditorError(
        "PDF export requires a TrueType Chinese font (PingFang/Heiti/WenQuanYi)"
    )


def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _version_from_row(row, source_document: dict | None = None) -> ResumeVersion:
    content = json.loads(row["content_json"])
    return ResumeVersion(
        version_id=row["version_id"],
        workspace_id=row["workspace_id"],
        profile_id=row["profile_id"],
        source_document_id=row["source_document_id"],
        parent_version_id=row["parent_version_id"],
        version_number=row["version_number"],
        content={
            key: tuple(normalize_resume_text(value) for value in values)
            for key, values in content.items()
        },
        document=normalize_resume_document(
            json.loads(row["document_json"])
            if row["document_json"]
            else source_document
        ),
        is_current=bool(row["is_current"]),
        original_file=bool(row["original_file"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
