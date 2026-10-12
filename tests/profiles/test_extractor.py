from __future__ import annotations

import io
import zipfile

import pytest
from pypdf import PdfWriter

from jobfindsme.profiles.parser import (
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
        content=make_docx("Projects: jobfindsme"),
    )

    assert extracted_markdown.text == "# Skills\nPython RAG"
    assert extracted_docx.text == "Projects: jobfindsme"


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


def test_pdf_private_font_bullet_becomes_portable_without_changing_source():
    from pypdf import PdfReader
    from pypdf.generic import NameObject, StreamObject

    # A real PDF ToUnicode map as emitted by WPS: the visible bullet is F0B7.
    reader = PdfReader(
        io.BytesIO(
            make_pdf_with_text(
                "B Experience building Python services and search tools."
            )
        )
    )
    writer = PdfWriter()
    writer.append(reader)
    cmap = StreamObject()
    cmap.set_data(b"""/CIDInit /ProcSet findresource begin
12 dict begin begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /WPSBullet def /CMapType 2 def
1 begincodespacerange <00> <FF> endcodespacerange
1 beginbfchar <42> <F0B7> endbfchar
endcmap CMapName currentdict /CMap defineresource pop end end""")
    font = writer.pages[0]["/Resources"]["/Font"]["/F1"]
    font[NameObject("/ToUnicode")] = writer._add_object(cmap)
    output = io.BytesIO()
    writer.write(output)
    source = output.getvalue()
    assert PdfReader(io.BytesIO(source)).pages[0].extract_text().startswith("\uf0b7")
    extracted = ResumeTextExtractor().extract(file_name="resume.pdf", content=source)
    assert extracted.text.startswith("• Experience")
    assert extracted.content == source


def test_only_known_line_leading_private_bullet_is_normalized():
    from jobfindsme.profiles.text import normalize_resume_text

    text = "\t\uf0b7 项目\n• 正常\n中间\uf0b7保留\n\ue123 未知符号\n  \uf0b7 second"
    assert normalize_resume_text(text) == (
        "\t• 项目\n• 正常\n中间\uf0b7保留\n\ue123 未知符号\n  • second"
    )
