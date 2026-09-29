import base64
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from jobfindsme.desktop_api import create_app


def test_attachment_extraction_is_authenticated_bounded_and_does_not_import_resume(
    tmp_path,
):
    client = TestClient(
        create_app(token="test-secret", database_path=tmp_path / "test.db")
    )
    headers = {"Authorization": "Bearer test-secret"}

    def request(name, content):
        return {"file_name": name, "content_base64": base64.b64encode(content).decode()}

    assert (
        client.post(
            "/v1/chat-attachments/extract", json=request("材料.txt", b"text")
        ).status_code
        == 401
    )
    before = client.get("/v1/resumes/state", headers=headers).json()
    for name in ("资料.md", "资料.txt"):
        response = client.post(
            "/v1/chat-attachments/extract",
            headers=headers,
            json=request(name, "真实贡献".encode()),
        )
        assert response.status_code == 200
        assert response.json() == {"text": "真实贡献", "truncated": False}
    pdf = BytesIO()
    canvas = Canvas(pdf)
    canvas.drawString(
        40,
        700,
        "Real project experience with API development and verified testing results",
    )
    canvas.save()
    response = client.post(
        "/v1/chat-attachments/extract",
        headers=headers,
        json=request("material.pdf", pdf.getvalue()),
    )
    assert response.status_code == 200
    assert "Real project experience" in response.json()["text"]
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>项目材料</w:t></w:r></w:p></w:body></w:document>',
        )
    response = client.post(
        "/v1/chat-attachments/extract",
        headers=headers,
        json=request("经历.docx", out.getvalue()),
    )
    assert response.status_code == 200
    assert "项目材料" in response.json()["text"]
    response = client.post(
        "/v1/chat-attachments/extract",
        headers=headers,
        json=request("long.txt", b"a" * 9000),
    )
    assert response.json() == {"text": "a" * 8000, "truncated": True}
    for name, content in (("坏.pdf", b"broken"), ("image.png", b"image")):
        assert (
            client.post(
                "/v1/chat-attachments/extract",
                headers=headers,
                json=request(name, content),
            ).status_code
            == 422
        )
    assert client.get("/v1/resumes/state", headers=headers).json() == before
