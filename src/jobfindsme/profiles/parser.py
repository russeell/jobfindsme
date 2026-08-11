"""Resume text extraction and deterministic parsing.

extractor: PDF/DOCX/MD/TXT text extraction.
parser: section-aware deterministic parsing into facts.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

from jobfindsme.profiles.models import FactType
from jobfindsme.taxonomy import SKILL_ALIASES

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 50
MIN_READABLE_PDF_CHARS = 30
MAX_DOCX_FILES = 500
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024


class ResumeExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedResume:
    file_name: str
    media_type: str
    content: bytes
    text: str


class ResumeTextExtractor:
    """Extract text from a small file allowlist without executing content."""

    def extract_path(self, source_path: str | Path) -> ExtractedResume:
        path = Path(source_path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ResumeExtractionError("resume path must be a file")
        return self.extract(file_name=path.name, content=path.read_bytes())

    def extract(self, *, file_name: str, content: bytes) -> ExtractedResume:
        safe_name = Path(file_name.replace("\\", "/")).name.strip()
        if not safe_name or safe_name in {".", ".."} or "\x00" in safe_name:
            raise ResumeExtractionError("invalid resume file name")
        if not content:
            raise ResumeExtractionError("resume file cannot be empty")
        if len(content) > MAX_RESUME_BYTES:
            raise ResumeExtractionError("resume file cannot exceed 5MB")

        suffix = Path(safe_name).suffix.lower()
        if suffix in {".txt", ".md"}:
            text = _decode_text(content)
            media_type = "text/markdown" if suffix == ".md" else "text/plain"
        elif suffix == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ResumeExtractionError("file content is not PDF")
            text = _extract_pdf(content)
            media_type = "application/pdf"
        elif suffix == ".docx":
            text = _extract_docx(content)
            media_type = (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        else:
            raise ResumeExtractionError("supported formats: PDF, DOCX, MD, TXT")

        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if not normalized:
            raise ResumeExtractionError("resume contains no readable text")
        return ExtractedResume(safe_name, media_type, content, normalized)


def _decode_text(content: bytes) -> str:
    """Decode text resumes with encoding fallback (GB18030 is the superset
    covering GBK/GB2312 — common for Chinese Windows-saved TXT resumes)."""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ResumeExtractionError(
        "text resume encoding not recognized (tried UTF-8 and GB18030)"
    )


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as error:
        raise ResumeExtractionError("invalid PDF") from error
    if reader.is_encrypted:
        raise ResumeExtractionError("encrypted PDF is not supported")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ResumeExtractionError("PDF cannot exceed 50 pages")
    try:
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as error:
        raise ResumeExtractionError("invalid PDF content") from error
    if len(text.strip()) < MIN_READABLE_PDF_CHARS:
        raise ResumeExtractionError(
            "PDF looks like a scanned image with no text layer; "
            "provide a text-based PDF or export it as DOCX/TXT"
        )
    return text


def _extract_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_FILES:
                raise ResumeExtractionError("invalid DOCX structure")
            if sum(item.file_size for item in entries) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ResumeExtractionError("DOCX expands beyond the size limit")
            document = archive.read("word/document.xml")
    except ResumeExtractionError:
        raise
    except (KeyError, zipfile.BadZipFile) as error:
        raise ResumeExtractionError("invalid DOCX") from error

    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise ResumeExtractionError("invalid DOCX XML") from error
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        value = "".join(
            node.text or "" for node in paragraph.iter(f"{namespace}t")
        ).strip()
        if value:
            paragraphs.append(value)
    return "\n".join(paragraphs)


SKILLS = {
    alias.casefold(): canonical
    for canonical, aliases in SKILL_ALIASES.items()
    for alias in (canonical, *aliases)
}

SECTION_PATTERNS: tuple[tuple[re.Pattern[str], FactType | None], ...] = (
    (
        re.compile(
            r"^(?:项目经历|项目经验|个人项目|独立项目|项目实践|projects?)$",
            re.I,
        ),
        FactType.PROJECT,
    ),
    (
        re.compile(
            r"^(?:工作经历|工作经验|实习经历|职业经历|独立实践与工作经历|experience)$",
            re.I,
        ),
        FactType.EXPERIENCE,
    ),
    (
        re.compile(r"^(?:教育经历|教育背景|学历信息|education)$", re.I),
        FactType.EDUCATION,
    ),
    (
        re.compile(
            r"^(?:专业技能|技能清单|技术栈|个人信息|基本信息|求职意向|"
            r"个人优势|自我评价|证书|获奖经历|skills?)$",
            re.I,
        ),
        None,
    ),
)

DATE_RANGE = re.compile(
    r"(?:19|20)\d{2}[./年-]\d{1,2}?"
    r".{0,8}(?:(?:19|20)\d{2}[./年-]\d{1,2}?|至今|现在|present)",
    re.I,
)


@dataclass(frozen=True)
class ParsedFact:
    fact_type: FactType
    value: str
    evidence_snippet: str
    evidence_start: int
    evidence_end: int


@dataclass(frozen=True)
class _Line:
    text: str
    start: int
    end: int


class DeterministicResumeParser:
    """Extract reviewable facts without treating every PDF line as a project."""

    version = "deterministic-resume-v3"

    def __init__(self) -> None:
        aliases = sorted(SKILLS, key=len, reverse=True)
        self.skill_pattern = re.compile(
            r"(?<![\w-])(" + "|".join(re.escape(item) for item in aliases) + r")"
            r"(?![\w-])",
            flags=re.IGNORECASE,
        )

    def parse(self, text: str) -> list[ParsedFact]:
        facts = self._skills(text)
        facts.extend(self._section_blocks(text))
        return _deduplicate(facts)

    def _skills(self, text: str) -> list[ParsedFact]:
        return [
            ParsedFact(
                fact_type=FactType.SKILL,
                value=SKILLS[match.group(0).casefold()],
                evidence_snippet=match.group(0),
                evidence_start=match.start(),
                evidence_end=match.end(),
            )
            for match in self.skill_pattern.finditer(text)
        ]

    def _section_blocks(self, text: str) -> list[ParsedFact]:
        lines = _lines(text)
        facts: list[ParsedFact] = []
        current_type: FactType | None = None
        current: list[_Line] = []

        def flush() -> None:
            if current_type is None or not current:
                current.clear()
                return
            for block in _split_entries(current):
                value = _normalize_block(block)
                if len(value) < 8:
                    continue
                start, end = block[0].start, block[-1].end
                facts.append(
                    ParsedFact(
                        fact_type=current_type,
                        value=value,
                        evidence_snippet=text[start:end],
                        evidence_start=start,
                        evidence_end=end,
                    )
                )
            current.clear()

        for line in lines:
            heading = _section_heading(line.text)
            if heading is not _NOT_A_HEADING:
                flush()
                current_type = heading
                continue
            if current_type is not None and line.text.strip():
                current.append(line)
        flush()
        return facts


_NOT_A_HEADING = object()


def _section_heading(value: str) -> FactType | None | object:
    normalized = value.strip().lstrip("#").strip().rstrip(":：").strip()
    for pattern, fact_type in SECTION_PATTERNS:
        if pattern.fullmatch(normalized):
            return fact_type
    return _NOT_A_HEADING


def _lines(text: str) -> list[_Line]:
    result = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if stripped:
            left = len(line) - len(line.lstrip())
            result.append(_Line(stripped, offset + left, offset + len(line.rstrip())))
        offset += len(raw)
    return result


def _split_entries(lines: list[_Line]) -> list[list[_Line]]:
    """Split on date-bearing headers; keep wrapped responsibility lines together."""

    entries: list[list[_Line]] = []
    current: list[_Line] = []
    for line in lines:
        starts_entry = bool(DATE_RANGE.search(line.text))
        if starts_entry and current:
            entries.append(current)
            current = []
        current.append(line)
    if current:
        entries.append(current)
    return entries


def _normalize_block(lines: list[_Line]) -> str:
    parts = [
        re.sub(r"^(?:[-*•·+]|\d+[.)、])\s*", "", line.text).strip() for line in lines
    ]
    return " ".join(part for part in parts if part)


def _deduplicate(facts: list[ParsedFact]) -> list[ParsedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value.casefold())
        if key not in seen:
            seen.add(key)
            result.append(fact)
    return result
