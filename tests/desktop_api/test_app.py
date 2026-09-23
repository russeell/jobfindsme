from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from fastapi.testclient import TestClient

from jobfindsme.desktop_api import create_app
from jobfindsme.models import ModelGateway
from jobfindsme.models.gateway import ModelGatewayError, TransportResponse
from jobfindsme.resume_editor import ResumeEditorService
from jobfindsme.storage import Database


def test_desktop_api_rejects_missing_and_wrong_tokens(tmp_path) -> None:
    app = create_app(token="test-secret", database_path=tmp_path / "desktop.db")
    client = TestClient(app)

    assert client.get("/health").status_code == 401
    assert client.get("/openapi.json").status_code == 404
    assert (
        client.get(
            "/health", headers={"Authorization": "Bearer wrong-secret"}
        ).status_code
        == 401
    )


def test_bootstrap_reads_real_core_and_enforces_source_gates(tmp_path) -> None:
    app = create_app(token="test-secret", database_path=tmp_path / "desktop.db")
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}

    response = client.get("/v1/bootstrap", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["workspaces"]) == 1
    repeated = client.get("/v1/bootstrap", headers=headers).json()
    assert repeated["workspaces"] == payload["workspaces"]
    sources = {item["source_id"]: item for item in payload["sources"]}
    assert sources["liepin"]["live_search_enabled"] is True
    assert sources["liepin"]["login_required"] is False
    for source_id in ("boss", "zhilian", "wuyou"):
        assert sources[source_id]["live_search_enabled"] is False
        assert sources[source_id]["login_required"] is True


def test_resume_import_confirmation_version_and_analysis_preview(tmp_path) -> None:
    database_path = tmp_path / "desktop.db"
    app = create_app(token="test-secret", database_path=database_path)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}
    source = tmp_path / "resume.md"
    source.write_text(
        "# Skills\nPython RAG\n# Projects\nContact me@example.com for details",
        encoding="utf-8",
    )

    imported = client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(source), "mode": "managed"},
    )
    assert imported.status_code == 200
    draft = imported.json()
    state = client.get("/v1/resumes/state", headers=headers).json()
    assert state["pending_confirmation"] is True
    assert state["search_profile_state"] == "pending_confirmation"
    assert state["search_block_reason"]
    assert state["capabilities"]["doc_status"] == "unsupported"
    assert state["capabilities"]["ocr_status"] == "unavailable"

    confirmed = client.post(
        f"/v1/resumes/{draft['profile_id']}/confirm",
        headers=headers,
        json={
            "workspace_id": state["workspace_id"],
            "accepted_fact_ids": [fact["fact_id"] for fact in draft["facts"]],
            "corrections": {},
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["current_version_number"] == 1
    assert confirmed.json()["search_profile_state"] == "ready"
    assert confirmed.json()["active_draft"] is None

    preview = client.post(
        "/v1/resumes/analysis-preview",
        headers=headers,
        json={
            "workspace_id": state["workspace_id"],
            "redacted_fields": ["email"],
        },
    )
    assert preview.status_code == 200
    assert "me@example.com" not in preview.json()["text"]
    assert "[已过滤:email]" in preview.json()["text"]

    default_preview = client.post(
        "/v1/resumes/analysis-preview",
        headers=headers,
        json={"workspace_id": state["workspace_id"]},
    )
    assert "me@example.com" not in default_preview.json()["text"]

    keep_preview = client.post(
        "/v1/resumes/analysis-preview",
        headers=headers,
        json={"workspace_id": state["workspace_id"], "privacy_mode": "keep"},
    )
    assert "me@example.com" in keep_preview.json()["text"]


def test_resume_editor_api_saves_and_restores_versions(tmp_path) -> None:
    app = create_app(token="test-secret", database_path=tmp_path / "desktop.db")
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}
    source = tmp_path / "resume.md"
    source.write_text("# Skills\nPython\n# Projects\n真实项目", encoding="utf-8")
    draft = client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(source)},
    ).json()
    confirmed = client.post(
        f"/v1/resumes/{draft['profile_id']}/confirm",
        headers=headers,
        json={
            "workspace_id": draft["workspace_id"],
            "accepted_fact_ids": [fact["fact_id"] for fact in draft["facts"]],
        },
    ).json()
    versions = client.get(
        "/v1/resume-versions",
        headers=headers,
        params={"workspace_id": draft["workspace_id"]},
    ).json()
    original = versions[0]
    content = {**original["content"], "skills": ["Python", "FastAPI"]}
    saved = client.post(
        "/v1/resume-versions",
        headers=headers,
        json={
            "workspace_id": draft["workspace_id"],
            "base_version_id": confirmed["current_version_id"],
            "content": content,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["content"]["skills"] == ["Python", "FastAPI"]
    restored = client.post(
        f"/v1/resume-versions/{original['version_id']}/restore",
        headers=headers,
        json={"workspace_id": draft["workspace_id"]},
    )
    assert restored.status_code == 200
    assert restored.json()["content"] == original["content"]
    current_id = restored.json()["version_id"]
    endpoint = f"/v1/resume-versions/{current_id}"
    workspace_params = {"workspace_id": draft["workspace_id"]}
    assert client.delete(
        endpoint, headers=headers, params=workspace_params
    ).status_code == 409
    with Database(tmp_path / "desktop.db").connect() as connection:
        connection.execute(
            "INSERT INTO scoring_rule_versions "
            "(rule_version_id, workspace_id, name, weights_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "rule-snapshot", draft["workspace_id"], "fixture", "{}",
                "2026-01-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO desktop_search_runs "
            "(run_id, workspace_id, resume_version_id, rule_version_id, "
            "intent, filter_snapshot_json, ordered_job_ids_json, "
            "scores_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-snapshot", draft["workspace_id"], saved.json()["version_id"],
             "rule-snapshot", "fixture", "{}", "[]", "{}", "2026-01-01T00:00:00Z",),
        )
    assert client.delete(
        f"/v1/resume-versions/{saved.json()['version_id']}",
        headers=headers, params=workspace_params,
    ).status_code == 409
    old_endpoint = f"/v1/resume-versions/{original['version_id']}"
    assert client.delete(
        old_endpoint, headers=headers, params={"workspace_id": "other"}
    ).status_code == 404
    assert client.delete(
        old_endpoint, headers=headers, params=workspace_params
    ).status_code == 200
    visible = client.get(
        "/v1/resume-versions", headers=headers, params=workspace_params
    ).json()
    assert {item["version_id"] for item in visible} == {
        saved.json()["version_id"], current_id
    }
    hidden = ResumeEditorService(Database(tmp_path / "desktop.db")).get_version(
        workspace_id=draft["workspace_id"], version_id=original["version_id"]
    )
    assert {key: list(value) for key, value in hidden.content.items()} == original[
        "content"
    ]


def test_prompt_resume_api_requires_verified_connection_and_saves_patch(
    tmp_path,
) -> None:
    captured = {}

    class PatchTransport:
        def post(self, **kwargs):
            captured["prompt"] = kwargs["payload"]["messages"][0]["content"]
            return TransportResponse(
                status=200,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "patches": [
                                            {
                                                "section": "projects",
                                                "before": ["实现本地真实求职项目"],
                                                "after": ["实现本地优先的真实求职项目"],
                                                "rationale": "明确已有约束",
                                                "evidence_ids": ["resume:projects:1"],
                                                "needs_user_input": [],
                                            }
                                        ]
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )

    database_path = tmp_path / "desktop.db"
    app = create_app(
        token="test-secret",
        database_path=database_path,
        model_gateway_override=ModelGateway(PatchTransport()),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}
    source = tmp_path / "resume.md"
    source.write_text(
        "zhangsan@example.com\n# Skills\nPython\n# Projects\n实现本地真实求职项目",
        encoding="utf-8",
    )
    draft = client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(source)},
    ).json()
    state = client.post(
        f"/v1/resumes/{draft['profile_id']}/confirm",
        headers=headers,
        json={
            "workspace_id": draft["workspace_id"],
            "accepted_fact_ids": [fact["fact_id"] for fact in draft["facts"]],
        },
    ).json()
    connection = client.post(
        "/v1/model-connections",
        headers=headers,
        json={
            "provider": "Offline fixture",
            "protocol": "openai_compatible",
            "endpoint": "https://model.example/v1",
            "model_id": "fixture-1",
            "credential_ref": "test-only",
        },
    ).json()
    blocked = client.post(
        "/v1/resume-edit-sessions",
        headers=headers,
        json={
            "workspace_id": draft["workspace_id"],
            "base_version_id": state["current_version_id"],
            "connection_id": connection["connection_id"],
        },
    )
    assert blocked.status_code == 409
    with Database(database_path).connect() as database:
        database.execute(
            "UPDATE model_connections SET status = 'verified' WHERE connection_id = ?",
            (connection["connection_id"],),
        )
    session = client.post(
        "/v1/resume-edit-sessions",
        headers=headers,
        json={
            "workspace_id": draft["workspace_id"],
            "base_version_id": state["current_version_id"],
            "connection_id": connection["connection_id"],
        },
    ).json()
    generated = client.post(
        f"/v1/resume-edit-sessions/{session['session_id']}/turns",
        headers=headers,
        json={
            "request_id": "resume-prompt-request-1",
            "api_key": "offline-only",
            "prompt": "联系 zhangsan@example.com 并优化表达",
            "project_facts": [],
        },
    )
    assert generated.status_code == 200, generated.text
    patch = generated.json()["patches"][0]
    assert "zhangsan@example.com" not in captured["prompt"]
    accepted = client.post(
        f"/v1/resume-edit-sessions/{session['session_id']}/patches/{patch['patch_id']}",
        headers=headers,
        json={"decision": "accepted"},
    )
    assert accepted.status_code == 200
    saved = client.post(
        f"/v1/resume-edit-sessions/{session['session_id']}/save",
        headers=headers,
        json={},
    )
    assert saved.status_code == 200
    assert saved.json()["content"]["projects"] == ["实现本地优先的真实求职项目"]


def test_model_configuration_never_persists_api_key_and_stays_unverified(
    tmp_path,
) -> None:
    database_path = tmp_path / "desktop.db"
    app = create_app(token="test-secret", database_path=database_path)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}

    response = client.post(
        "/v1/model-connections",
        headers=headers,
        json={
            "provider": "Example",
            "protocol": "openai_compatible",
            "endpoint": "https://model.example/v1",
            "model_id": "example-1",
        },
    )

    assert response.status_code == 200
    connection = response.json()
    assert connection["status"] == "unverified"
    assert "api_key" not in connection
    assert "secret-key" not in database_path.read_bytes().decode(
        "utf-8", errors="ignore"
    )

    assert connection["credential_ref"] is None


def test_latest_resume_draft_can_be_recovered_confirmed_or_abandoned(tmp_path) -> None:
    app = create_app(token="test-secret", database_path=tmp_path / "desktop.db")
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("Python", encoding="utf-8")
    second.write_text("Docker", encoding="utf-8")

    client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(first)},
    )
    latest = client.post(
        "/v1/resumes/import",
        headers=headers,
        json={"source_path": str(second)},
    ).json()
    state = client.get("/v1/resumes/state", headers=headers).json()
    assert state["active_draft"]["profile_id"] == latest["profile_id"]

    abandoned = client.post(
        f"/v1/resumes/{latest['profile_id']}/abandon",
        params={"workspace_id": latest["workspace_id"]},
        headers=headers,
        json={},
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["search_profile_state"] == "no_resume"
    assert abandoned.json()["active_draft"] is None


def test_cancel_closes_active_model_transport_and_preserves_cancelled_state(
    tmp_path,
) -> None:
    started = threading.Event()
    released = threading.Event()

    class BlockingTransport:
        def post(self, **kwargs):
            kwargs["cancellation"].register(released.set)
            started.set()
            assert released.wait(timeout=2)
            kwargs["cancellation"].raise_if_cancelled()
            return TransportResponse(status=200, payload={})

    app = create_app(
        token="test-secret",
        database_path=tmp_path / "desktop.db",
        model_gateway_override=ModelGateway(BlockingTransport()),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}
    connection = client.post(
        "/v1/model-connections",
        headers=headers,
        json={
            "provider": "Example",
            "protocol": "openai_compatible",
            "endpoint": "https://model.example/v1",
            "model_id": "example-1",
        },
    ).json()
    test_id = "model-test-cancellation-1"
    result = {}

    def run_test() -> None:
        result["response"] = client.post(
            f"/v1/model-connections/{connection['connection_id']}/test",
            headers=headers,
            json={"test_id": test_id, "api_key": "not-real", "timeout_seconds": 5},
        )

    thread = threading.Thread(target=run_test)
    thread.start()
    assert started.wait(timeout=2)
    cancelled = client.post(
        f"/v1/model-connections/{connection['connection_id']}/tests/{test_id}/cancel",
        headers=headers,
        json={},
    )
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert cancelled.json()["status"] == "cancelled"
    assert result["response"].json()["status"] == "cancelled"


def test_model_timeout_is_recorded_as_failed_status(tmp_path) -> None:
    class TimeoutTransport:
        def post(self, **kwargs):
            raise ModelGatewayError("model endpoint timed out")

    app = create_app(
        token="test-secret",
        database_path=tmp_path / "desktop.db",
        model_gateway_override=ModelGateway(TimeoutTransport()),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-secret"}
    connection = client.post(
        "/v1/model-connections",
        headers=headers,
        json={
            "provider": "Example",
            "protocol": "openai_compatible",
            "endpoint": "https://model.example/v1",
            "model_id": "example-1",
        },
    ).json()
    response = client.post(
        f"/v1/model-connections/{connection['connection_id']}/test",
        headers=headers,
        json={
            "test_id": "model-test-timeout-1",
            "api_key": "not-real",
            "timeout_seconds": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["last_error"] == "model endpoint timed out"


def test_desktop_api_process_starts_and_stops_cleanly(tmp_path) -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    token = "process-test-secret"
    env = {**os.environ, "JFM_DESKTOP_TOKEN": token}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "jobfindsme.desktop_api",
            "--port",
            str(port),
            "--database",
            str(tmp_path / "process.db"),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/health",
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=1) as response:
                    assert response.status == 200
                    break
            except OSError as error:
                if process.poll() is not None:
                    stderr = process.stderr.read() if process.stderr else ""
                    raise AssertionError(
                        f"desktop API exited early: {stderr}"
                    ) from error
                time.sleep(0.05)
        else:
            raise AssertionError("desktop API did not start within 8 seconds")
    finally:
        process.terminate()
        process.wait(timeout=5)

    # Electron uses SIGTERM for shutdown; uvicorn may either handle it or the
    # OS may report the terminating signal when the probe races its handler.
    assert process.returncode in {0, -15}
