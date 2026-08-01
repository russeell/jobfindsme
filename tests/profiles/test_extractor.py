from __future__ import annotations

import io
import zipfile

import pytest
from pypdf import PdfWriter

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


def make_pdf_with_text(text: str) -> bytes:
    """Programmatic single-page PDF with a text layer (pypdf-generated)."""
    from pypdf.generic import (
        DictionaryObject,
        NameObject,
        StreamObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=144)
    content = StreamObject()
    content.set_data(f"BT /F1 18 Tf 0 0 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(content)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def make_scanned_pdf() -> bytes:
    """Blank page with no content stream — what a scanned PDF yields."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
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


def test_decodes_gbk_text_resume() -> None:
    """Chinese Windows TXT resumes are GBK/GB18030, not UTF-8."""
    content = "姓名：张三\n技能：Python、FastAPI".encode("gb18030")

    extracted = ResumeTextExtractor().extract(
        file_name="resume.txt",
        content=content,
    )

    assert extracted.text == "姓名：张三\n技能：Python、FastAPI"


def test_extracts_text_pdf() -> None:
    text = "Hello World, resume with Python and FastAPI experience."
    extracted = ResumeTextExtractor().extract(
        file_name="resume.pdf",
        content=make_pdf_with_text(text),
    )

    assert "Python" in extracted.text


def test_rejects_scanned_pdf() -> None:
    with pytest.raises(ResumeExtractionError, match="scanned image"):
        ResumeTextExtractor().extract(
            file_name="resume.pdf",
            content=make_scanned_pdf(),
        )


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
