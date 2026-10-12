"""Recover portable typography from retained originals without changing facts.

PDF geometry, drawings and embedded fonts stay in the original preview. This
module maps character styles to exact text matches in the editable copy. It
never guesses new resume text or reads an unretained source path.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jobfindsme.profiles.models import FactType
from jobfindsme.profiles.parser import (
    MAX_DOCX_FILES,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_PDF_PAGES,
    MAX_RESUME_BYTES,
    _section_heading,
)
from jobfindsme.resume_editor.document import (
    document_content,
    reconcile_document,
    validate_document,
)

MAX_STYLE_CHARS = 60_000
SECTION_KEYS = {
    FactType.BASIC_INFORMATION: "basic_information",
    FactType.EDUCATION: "education",
    FactType.EXPERIENCE: "experience",
    FactType.PROJECT: "projects",
    FactType.SKILL_DETAIL: "skills",
}


@dataclass(frozen=True)
class StyledLine:
    text: str
    # One tuple of marks per character; whitespace remains the fact's own text.
    marks: tuple[tuple, ...]
    align: str | None = None


def _marks(color=None, size=None, *, bold=False, italic=False, underline=False):
    marks = []
    for name, enabled in (("bold", bold), ("italic", italic), ("underline", underline)):
        if enabled:
            marks.append((name,))
    attrs = {}
    if color:
        attrs["color"] = color
    if size is not None and 6 <= size <= 72:
        attrs["fontSize"] = round(size, 2)
    if attrs:
        marks.append(("textStyle", tuple(sorted(attrs.items()))))
    return tuple(marks)


def _rgb(value):
    if isinstance(value, (int, float)):
        channels = [value] * 3
    elif isinstance(value, (list, tuple)) and len(value) in (1, 3, 4):
        if len(value) == 1:
            channels = list(value) * 3
        elif len(value) == 4:
            c, m, y, k = value
            channels = [1 - min(1, v + k) for v in (c, m, y)]
        else:
            channels = value
    else:
        return None
    return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02x}" for v in channels)


def _pdf_lines(content: bytes) -> tuple[StyledLine, ...]:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTTextLine

    lines = []
    count = 0

    def walk(node):
        nonlocal count
        if isinstance(node, LTTextLine):
            text, styles = [], []
            for child in node:
                value = child.get_text() if hasattr(child, "get_text") else ""
                count += len(value)
                if count > MAX_STYLE_CHARS:
                    raise ValueError("resume style text exceeds limit")
                marks = ()
                if isinstance(child, LTChar):
                    font = child.fontname.casefold()
                    marks = _marks(
                        _rgb(child.graphicstate.ncolor),
                        child.size,
                        bold=bool(
                            re.search(
                                r"bold|black|heavy|semibold|demi|[-+]w[6-9]", font
                            )
                        ),
                        italic=bool(re.search(r"italic|oblique", font)),
                    )
                text.extend(value)
                styles.extend([marks] * len(value))
            lines.append(StyledLine("".join(text), tuple(styles)))
        elif hasattr(node, "__iter__"):
            for child in node:
                walk(child)

    for page in extract_pages(io.BytesIO(content), maxpages=MAX_PDF_PAGES + 1):
        if page.pageid > MAX_PDF_PAGES:
            raise ValueError("too many resume pages")
        walk(page)
    return tuple(lines)


def _docx_lines(content: bytes) -> tuple[StyledLine, ...]:
    import zipfile

    from docx import Document

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        if (
            len(entries) > MAX_DOCX_FILES
            or sum(e.file_size for e in entries) > MAX_DOCX_UNCOMPRESSED_BYTES
        ):
            raise ValueError("invalid DOCX structure")
    document = Document(io.BytesIO(content))

    # Document.iter_inner_content keeps paragraphs/tables in authored order.
    def paragraphs(items):
        for item in items:
            if hasattr(item, "runs"):
                yield item
            elif hasattr(item, "rows"):
                for row in item.rows:
                    for cell in row.cells:
                        yield from paragraphs(cell.iter_inner_content())

    result = []
    count = 0
    for p in paragraphs(document.iter_inner_content()):
        text, styles = [], []
        for run in p.runs:
            fonts = [run.font]
            for start in (run.style, p.style):
                seen = set()
                while start is not None and start.style_id not in seen:
                    seen.add(start.style_id)
                    fonts.append(start.font)
                    start = start.base_style

            def effective(name, fonts=fonts):
                return next(
                    (getattr(f, name) for f in fonts if getattr(f, name) is not None),
                    None,
                )

            color = next((f.color.rgb for f in fonts if f.color.rgb is not None), None)
            size = effective("size")
            marks = _marks(
                f"#{color}".lower() if color else None,
                size.pt if size else None,
                bold=effective("bold"),
                italic=effective("italic"),
                underline=effective("underline"),
            )
            text.extend(run.text)
            styles.extend([marks] * len(run.text))
            count += len(run.text)
            if count > MAX_STYLE_CHARS:
                raise ValueError("resume style text exceeds limit")
        alignment = (
            p.alignment
            if p.alignment is not None
            else p.style.paragraph_format.alignment
        )
        align = {0: "left", 1: "center", 2: "right", 3: "justify"}.get(alignment)
        result.append(StyledLine("".join(text), tuple(styles), align))
    return tuple(result)


@lru_cache(maxsize=4)
def _source_lines(content: bytes, suffix: str) -> tuple[StyledLine, ...]:
    if suffix == ".pdf":
        return _pdf_lines(content)
    if suffix == ".docx":
        return _docx_lines(content)
    return ()


def _compact(text):
    return "".join(c.replace("\uf0b7", "•") for c in text if not c.isspace())


def import_document(content: dict, source: bytes, suffix: str) -> dict:
    lines = _source_lines(source, suffix)
    document = reconcile_document(content)
    compact, styles, line_indexes = [], [], []
    for i, line in enumerate(lines):
        for char, marks in zip(line.text, line.marks, strict=True):
            if not char.isspace():
                compact.append(char.replace("\uf0b7", "•"))
                styles.append(marks)
                line_indexes.append(i)
    searchable = "".join(compact)
    headings = {}
    for line in lines:
        section = SECTION_KEYS.get(_section_heading(line.text))
        if section and line.text.strip():
            dominant = Counter(m for m in line.marks if m).most_common(1)
            if dominant:
                attrs = next(
                    (dict(m[1]) for m in dominant[0][0] if m[0] == "textStyle"), {}
                )
                headings[section] = attrs
    cursor = 0
    styled = False
    for section in document["content"]:
        key = section["attrs"]["section"]
        heading = headings.get(key, {})
        for source_key, target_key in (
            ("color", "headingColor"),
            ("fontSize", "headingSize"),
        ):
            if source_key in heading:
                section["attrs"][target_key] = heading[source_key]
        for block in section["content"]:
            children = []
            for child in block["content"]:
                if child["type"] != "text":
                    children.append(child)
                    continue
                text = child["text"]
                query = _compact(text)
                pos = searchable.find(query, cursor) if query else -1
                if pos < 0 and query:
                    pos = searchable.find(query)
                if pos < 0:
                    children.append(child)
                    continue
                cursor = pos + len(query)
                matched = styles[pos:cursor]
                index = 0
                for char in text:
                    marks = matched[min(index, len(matched) - 1)]
                    if not char.isspace():
                        index += 1
                    encoded = [
                        {"type": m[0], **({"attrs": dict(m[1])} if len(m) > 1 else {})}
                        for m in marks
                    ]
                    styled |= bool(encoded)
                    if (
                        children
                        and children[-1]["type"] == "text"
                        and children[-1].get("marks", []) == encoded
                    ):
                        children[-1]["text"] += char
                    else:
                        children.append(
                            {
                                "type": "text",
                                "text": char,
                                **({"marks": encoded} if encoded else {}),
                            }
                        )
                align = lines[line_indexes[pos]].align
                if align:
                    block["attrs"] = {"textAlign": align}
            block["content"] = children
    if styled and "basic_information" not in headings:
        document["content"][0]["attrs"]["headingHidden"] = True
    result = validate_document(document)
    # The index and AI always see the same facts, regardless of source styling.
    if document_content(result) != document_content(reconcile_document(content)):
        raise ValueError("source formatting changed resume facts")
    return result


def retained_document(connection, row, *, data_root: Path) -> dict | None:
    if row["document_json"] or not row["original_file"]:
        return None
    source = connection.execute(
        "SELECT managed_path,content_hash,file_name FROM source_documents "
        "WHERE document_id=? AND workspace_id=?",
        (row["source_document_id"], row["workspace_id"]),
    ).fetchone()
    if source is None or not source["managed_path"]:
        return None
    try:
        path = Path(source["managed_path"]).resolve(strict=True)
        if path.parent != (data_root / "documents/managed").resolve():
            return None
        if not 0 < path.stat().st_size <= MAX_RESUME_BYTES:
            return None
        suffix = Path(source["file_name"]).suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            return None
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["content_hash"]:
            return None
        import json

        from jobfindsme.profiles.text import normalize_resume_text

        content = {
            k: [normalize_resume_text(v) for v in values]
            for k, values in json.loads(row["content_json"]).items()
        }
        return import_document(content, raw, suffix)
    except Exception:
        # Original preview/download remains usable if typography is unsupported.
        # No history is rewritten, no unverified replacement is persisted.
        return None
