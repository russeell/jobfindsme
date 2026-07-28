from __future__ import annotations

import io
import zipfile

import pytest

from jobfindsme.profiles.extractor import (
    MAX_RESUME_BYTES,
    ResumeExtractionError,
    ResumeTextExtractor,
)


def make_docx(text: str) -> bytes:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="'
        'http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def test_extracts_utf8_text_and_docx(tmp_path) -> None:
    markdown = tmp_path / "resume.md"
    markdown.write_text("# Skills\nPython RAG", encoding="utf-8")

    extracted_markdown = ResumeTextExtractor().extract_path(markdown)
    extracted_docx = ResumeTextExtractor().extract(
        file_name="resume.docx",
        content=make_docx("Projects: JobFindsMe"),
    )

    assert extracted_markdown.text == "# Skills\nPython RAG"
    assert extracted_docx.text == "Projects: JobFindsMe"


@pytest.mark.parametrize(
    ("file_name", "content"),
    [
        ("resume.exe", b"no"),
        ("resume.pdf", b"not a PDF"),
        ("resume.txt", b"\xff\xfe"),
        ("resume.docx", b"not a zip"),
    ],
)
def test_rejects_unsupported_or_invalid_content(
    file_name: str,
    content: bytes,
) -> None:
    with pytest.raises(ResumeExtractionError):
        ResumeTextExtractor().extract(file_name=file_name, content=content)


def test_rejects_oversized_resume() -> None:
    with pytest.raises(ResumeExtractionError, match="5MB"):
        ResumeTextExtractor().extract(
            file_name="resume.txt",
            content=b"x" * (MAX_RESUME_BYTES + 1),
        )
