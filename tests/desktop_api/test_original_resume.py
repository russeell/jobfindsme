import base64

import pytest
from fastapi.testclient import TestClient

from jobfindsme.desktop_api import create_app
from jobfindsme.resume_editor import ResumeEditorService
from jobfindsme.storage import Database


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_desktop_import_indexes_locally_and_serves_only_scoped_original(
    tmp_path, newline
):
    client = TestClient(create_app(token="test", database_path=tmp_path / "test.db"))
    headers = {"Authorization": "Bearer test"}
    source = tmp_path / "synthetic.md"
    original = "# Projects\n虚构岗位检索工具，Python 开发。\n# Skills\nPython"
    original_bytes = original.replace("\n", newline).encode("utf-8")
    source.write_bytes(original_bytes)
    response = client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(source), "mode": "managed", "index_original": True},
    )
    assert response.status_code == 200
    draft = response.json()
    state = client.get("/v1/resumes/state", headers=headers).json()
    assert state["active_draft"] is None and not state["pending_confirmation"]
    assert state["search_profile_state"] == "ready"
    workspace = state["workspace_id"]
    versions = client.get(
        "/v1/resume-versions", headers=headers, params={"workspace_id": workspace}
    ).json()
    assert versions[0]["original_file"]
    params = {"workspace_id": workspace, "document_id": draft["document_id"]}
    url = "/v1/resumes/source/file"
    assert client.get(url, params=params).status_code == 401
    response = client.get(url, headers=headers, params=params)
    assert response.status_code == 200
    assert base64.b64decode(response.json()["content_base64"]) == original_bytes
    assert "managed_path" not in response.text and str(tmp_path) not in response.text
    assert (
        client.get(
            url, headers=headers, params={**params, "workspace_id": "other"}
        ).status_code
        == 404
    )
    analysis = client.get(
        "/v1/research-agent/resume", headers=headers, params={"workspace_id": workspace}
    ).json()
    assert "不代表用户逐项确认" in analysis["limitations"]


def test_archived_original_can_be_resolved_exactly_without_changing_source(tmp_path):
    database_path = tmp_path / "test.db"
    client = TestClient(create_app(token="test", database_path=database_path))
    headers = {"Authorization": "Bearer test"}
    source = tmp_path / "original.md"
    original = b"# Skills\r\nPython FastAPI\r\n"
    source.write_bytes(original)
    imported = client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(source), "mode": "managed", "index_original": True},
    )
    assert imported.status_code == 200
    workspace = client.get("/v1/resumes/state", headers=headers).json()["workspace_id"]
    editor = ResumeEditorService(Database(database_path))
    version = editor.list_versions(workspace_id=workspace)[0]
    editor.save_edit(
        workspace_id=workspace,
        base_version_id=version.version_id,
        content=version.content,
        document=version.document,
    )
    editor.hide_version(workspace_id=workspace, version_id=version.version_id)
    assert version.version_id not in {
        row["version_id"]
        for row in client.get(
            "/v1/resume-versions", headers=headers, params={"workspace_id": workspace}
        ).json()
    }
    url = f"/v1/resume-versions/{version.version_id}"
    response = client.get(url, headers=headers, params={"workspace_id": workspace})
    assert response.status_code == 200
    assert response.json()["original_file"] is True
    assert response.json()["source_document_id"] == imported.json()["document_id"]
    assert client.get(url, params={"workspace_id": workspace}).status_code == 401
    assert (
        client.get(url, headers=headers, params={"workspace_id": "other"}).status_code
        == 404
    )
    source_response = client.get(
        "/v1/resumes/source/file",
        headers=headers,
        params={
            "workspace_id": workspace,
            "document_id": response.json()["source_document_id"],
        },
    )
    assert base64.b64decode(source_response.json()["content_base64"]) == original
