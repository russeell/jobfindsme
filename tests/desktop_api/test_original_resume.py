import base64

from fastapi.testclient import TestClient

from jobfindsme.desktop_api import create_app


def test_desktop_import_indexes_locally_and_serves_only_scoped_original(tmp_path):
    client = TestClient(create_app(token="test", database_path=tmp_path / "test.db"))
    headers = {"Authorization": "Bearer test"}
    source = tmp_path / "synthetic.md"
    original = "# Projects\n虚构岗位检索工具，Python 开发。\n# Skills\nPython"
    source.write_text(original)
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
    assert base64.b64decode(response.json()["content_base64"]).decode() == original
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
