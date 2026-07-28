from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 50
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
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ResumeExtractionError("text resume must use UTF-8") from error


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as error:
        raise ResumeExtractionError("invalid PDF") from error
    if reader.is_encrypted:
        raise ResumeExtractionError("encrypted PDF is not supported")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ResumeExtractionError("PDF cannot exceed 50 pages")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


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
