import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jobfindsme.desktop_api import create_app
from jobfindsme.desktop_api.app import ResearchRunRequest
from jobfindsme.research import agent_sources
from jobfindsme.research.agent_store import ResearchAgentStore
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def setup_store(tmp_path):
    database = Database(tmp_path / "agent.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    return ResearchAgentStore(database), workspace.workspace_id


def evidence(url="https://www.zhihu.com/p/123", text="示例公司在上海设立了研发团队，并公开介绍了产品方向。"):
    return {"evidence_id": "ev_test", "url": url, "platform": "知乎",
            "published_at": None, "retrieved_at": datetime.now(UTC).isoformat(),
            "company": "示例公司", "team": None, "excerpt": text,
            "evidence_kind": "public_source", "verification_status": "independently_retrieved",
            "relevance": "company", "limitations": "原页已读取，法律主体未知。",
            "context": {"source_type": "personal_account", "research_topic": "company"},
            "status": "read_original"}


def test_conversation_execution_and_report_are_workspace_scoped(tmp_path):
    store, workspace = setup_store(tmp_path)
    other = WorkspaceService(store.database).create().workspace_id
    chat = store.save_conversation(workspace, {"id": "c1", "turns": [{"role": "user", "text": "示例公司如何"}], "subject_company": "示例公司"})
    assert store.list_conversations(workspace)[0]["turns"] == chat["turns"]
    assert store.list_conversations(other) == []
    with pytest.raises(PermissionError):
        store.save_conversation(other, {"id": "c1", "turns": []})
    store.save_execution(workspace, {"id": "x1", "subject_key": "示例公司|", "status": "cancelled", "evidence": [evidence()], "actions": [{"tool": "read_page"}]})
    found = store.find_evidence(workspace, "示例公司")
    assert len(found) == 1 and store.find_evidence(other, "示例公司") == []
    report = {"company": "示例公司", "question": "研发方向", "evidence": [evidence()],
              "claims": [{"quote": "示例公司在上海设立了研发团队", "evidence_ids": ["ev_test"], "category": "business", "scope": "上海"}]}
    report_id = store.save_report(workspace, report)
    assert report_id and store.save_report(workspace, report) is None
    with pytest.raises(ValueError):
        store.save_report(workspace, {**report, "claims": [{"quote": "这是模型编造的事实", "evidence_ids": ["ev_test"]}]})
    with store.database.connect() as connection:
        saved = connection.execute("SELECT job_context_json FROM research_reports WHERE report_id=?", (report_id,)).fetchone()
    assert report_id in saved["job_context_json"]


def test_long_conversation_and_binding_round_trip_without_truncation(tmp_path):
    store, workspace = setup_store(tmp_path)
    turns = [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "text": f"第{index}轮" + "回答" * 1000,
        }
        for index in range(30)
    ]
    turns.append({"role": "assistant", "text": "最终回答" + "结论" * 2000})
    store.save_conversation(
        workspace,
        {
            "id": "long-chat",
            "job_id": "job-a",
            "subject_company": "A公司",
            "subject_title": "A岗位",
            "research_mode": True,
            "turns": turns,
        },
    )
    saved = store.list_conversations(workspace)[0]
    assert saved["turns"] == turns
    assert (
        saved["job_id"],
        saved["subject_company"],
        saved["subject_title"],
        saved["research_mode"],
    ) == ("job-a", "A公司", "A岗位", True)
    with pytest.raises(ValueError, match="700"):
        store.save_conversation(
            workspace, {"id": "too-long", "turns": [], "draft": "问" * 701}
        )


def test_frontend_stored_payload_round_trips_220_turns_via_api_after_restart(tmp_path):
    fixture = json.loads(
        (
            Path(__file__).parents[1] / "fixtures" / "research_chat_to_stored.json"
        ).read_text(encoding="utf-8")
    )
    store, workspace = setup_store(tmp_path)
    turns = []
    for index in range(110):
        turns.append({"role": "user", "text": f"第{index}轮：示例公司研发如何？"})
        turns.append(
            {
                "role": "assistant",
                "text": f"第{index}轮：" + fixture["turns"][1]["text"],
            }
        )
    payload = {**fixture, "workspace_id": workspace, "turns": turns}
    client = TestClient(
        create_app(token="test-secret", database_path=store.database.path)
    )
    response = client.put(
        "/v1/research-agent/conversations",
        headers={"Authorization": "Bearer test-secret"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert len(turns) > 200
    assert all(len(turns[index]["text"]) > 8000 for index in range(1, 30, 2))
    reopened = TestClient(
        create_app(token="test-secret", database_path=store.database.path)
    )
    listed = reopened.get(
        "/v1/research-agent/conversations",
        headers={"Authorization": "Bearer test-secret"},
        params={"workspace_id": workspace},
    )
    assert listed.status_code == 200
    saved = listed.json()[0]
    assert saved["turns"] == turns
    assert saved["job_id"] == fixture["job_id"]
    assert saved["subject_company"] == fixture["subject_company"]
    assert saved["research_mode"] is True


def test_conversation_storage_rejects_oversize_payload_without_truncation(tmp_path):
    store, workspace = setup_store(tmp_path)
    with pytest.raises(ValueError, match="16 MB"):
        store.save_conversation(
            workspace,
            {
                "id": "oversize",
                "turns": [{"role": "assistant", "text": "x" * 95000}] * 175,
            },
        )
    assert store.list_conversations(workspace) == []


def test_research_question_boundary_is_700_across_python_request_and_report(tmp_path):
    store, workspace = setup_store(tmp_path)
    for size in (300, 301, 700):
        request = ResearchRunRequest.model_validate(
            {"workspace_id": workspace, "interest_question": "问" * size}
        )
        assert len(request.interest_question) == size
    with pytest.raises(ValueError):
        ResearchRunRequest.model_validate(
            {"workspace_id": workspace, "interest_question": "问" * 701}
        )
    with pytest.raises(ValueError, match="invalid Agent report"):
        store.save_report(
            workspace,
            {"company": "示例公司", "question": "问" * 701, "evidence": [evidence()]},
        )


def test_search_endpoint_keeps_original_question_separate_from_query(
    tmp_path, monkeypatch
):
    import importlib

    app_module = importlib.import_module("jobfindsme.desktop_api.app")
    store, workspace = setup_store(tmp_path)
    seen = []
    monkeypatch.setattr(
        app_module,
        "discover_sources",
        lambda company, query, site: seen.append((company, query, site)) or [],
    )
    client = TestClient(
        create_app(token="test-secret", database_path=store.database.path)
    )
    for size in (300, 301, 700):
        response = client.post(
            "/v1/research-agent/search",
            headers={"Authorization": "Bearer test-secret"},
            json={
                "workspace_id": workspace,
                "company": "示例公司",
                "original_question": "问" * size,
                "search_query": "查" * size,
                "site": "zhihu",
            },
        )
        assert response.status_code == 200
    assert len(seen) == 3
    assert [len(query) for _, query, _ in seen] == [300, 301, 700]
    response = client.post(
        "/v1/research-agent/search",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace,
            "company": "示例公司",
            "original_question": "问" * 701,
            "search_query": "研发团队",
            "site": "zhihu",
        },
    )
    assert response.status_code == 400
    assert len(seen) == 3
    response = client.post(
        "/v1/research-agent/search",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace,
            "company": "示例公司",
            "original_question": "问" * 700,
            "search_query": "查" * 701,
            "site": "zhihu",
        },
    )
    assert response.status_code == 400
    assert len(seen) == 3


def test_new_supported_conclusion_versions_without_new_page(tmp_path):
    store, workspace = setup_store(tmp_path)
    base = {"company": "示例公司", "question": "研发方向", "evidence": [evidence()],
            "claims": [{"statement": "示例公司在上海设立研发团队", "quote": "示例公司在上海设立了研发团队",
                        "evidence_ids": ["ev_test"], "category": "business", "scope": "上海"}]}
    first = store.save_report(workspace, base)
    assert first and store.save_report(workspace, base) is None
    changed = {**base, "question": "产品方向", "claims": [{"statement": "示例公司在上海设立了研发团队，并公开介绍了产品方向",
              "quote": "示例公司在上海设立了研发团队，并公开介绍了产品方向",
              "evidence_ids": ["ev_test"], "category": "development", "scope": "团队、地区或法律主体未核实"}]}
    second = store.save_report(workspace, changed)
    assert second and second != first and store.save_report(workspace, changed) is None


@pytest.mark.parametrize("statement,quote,scope", [
    ("另一家公司在上海设立研发团队", "示例公司在上海设立了研发团队", "上海"),
    ("示例公司未在上海设立研发团队", "示例公司在上海设立了研发团队", "上海"),
    ("示例公司目前在上海设立研发团队", "示例公司在上海设立了研发团队", "上海"),
    ("示例公司在全国设立研发团队", "示例公司在上海设立了研发团队", "全国"),
    ("示例公司已上市", "示例公司计划上市", "团队、地区或法律主体未核实"),
])
def test_unsupported_entity_negation_time_scope_and_listing_are_rejected(tmp_path, statement, quote, scope):
    store, workspace = setup_store(tmp_path)
    source = evidence(text="示例公司在上海设立了研发团队，并公开介绍了产品方向。示例公司计划上市。")
    report = {"company": "示例公司", "evidence": [source], "claims": [
        {"statement": statement, "quote": quote, "evidence_ids": ["ev_test"], "category": "business", "scope": scope}
    ]}
    with pytest.raises(ValueError):
        store.save_report(workspace, report)


def test_source_url_blocks_wrong_host_and_private_address(monkeypatch):
    monkeypatch.setattr(agent_sources, "validate_public_http_url", lambda url, **kwargs: (_ for _ in ()).throw(ValueError("private")) if "private" in url else None)
    with pytest.raises(ValueError):
        agent_sources._source_url("https://attacker.example/p", "zhihu")
    with pytest.raises(ValueError):
        agent_sources._source_url("http://www.zhihu.com/p/123", "zhihu")
    with pytest.raises(ValueError):
        agent_sources._source_url("https://www.zhihu.com/private", "zhihu")


def test_original_read_only_counts_anchored_html(monkeypatch):
    monkeypatch.setattr(agent_sources, "validate_public_http_url", lambda *_args, **_kwargs: None)
    class Response:
        headers = SimpleNamespace(get_content_type=lambda: "text/html", get_content_charset=lambda: "utf-8")
        def geturl(self): return "https://www.zhihu.com/p/123"
        def read(self, _size): return '<html><head><title>示例公司项目</title></head><body><article>示例公司在上海设立研发团队，并介绍产品方向和业务历史。这里是更多说明。公司还介绍了产品团队、技术团队、客户服务团队以及业务模式的发展历程和年度规划。</article></body></html>'.encode()
        def __enter__(self): return self
        def __exit__(self, *_args): pass
    result = agent_sources.read_original_page("https://www.zhihu.com/p/123", "示例公司", "zhihu", opener=SimpleNamespace(open=lambda *_args, **_kwargs: Response()))
    assert result["status"] == "read_original" and result["verification_status"] == "independently_retrieved"
    assert result["published_at"] is None


def test_pdf_reader_keeps_page_citation_and_rejects_missing_entity(monkeypatch):
    import io
    from reportlab.pdfgen import canvas

    monkeypatch.setattr(agent_sources, "validate_public_http_url", lambda *_args, **_kwargs: None)
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(30, 700, "Other company annual filing")
    pdf.showPage()
    pdf.drawString(30, 700, "ExampleCorp reported revenue for 2025. ExampleCorp disclosed its research team and operations in this filing.")
    pdf.save()
    body = output.getvalue()

    class Response:
        headers = SimpleNamespace(get_content_type=lambda: "application/pdf", get_content_charset=lambda: None)
        def geturl(self): return "https://www.cninfo.com.cn/report.pdf"
        def read(self, amount): return body[:amount]
        def __enter__(self): return self
        def __exit__(self, *_args): pass

    opener = SimpleNamespace(open=lambda *_args, **_kwargs: Response())
    found = agent_sources.read_original_page("https://www.cninfo.com.cn/report.pdf", "ExampleCorp", "cninfo", opener=opener)
    assert found["status"] == "read_original"
    assert found["context"]["page"] == 2
    assert found["context"]["content_type"] == "application/pdf"
    assert "ExampleCorp" in found["excerpt"]
    missing = agent_sources.read_original_page("https://www.cninfo.com.cn/report.pdf", "UnrelatedCo", "cninfo", opener=opener)
    assert missing["status"] == "entity_mismatch"


def test_pdf_reader_rejects_large_or_unreadable_document(monkeypatch):
    monkeypatch.setattr(agent_sources, "validate_public_http_url", lambda *_args, **_kwargs: None)
    class Response:
        headers = SimpleNamespace(get_content_type=lambda: "application/pdf", get_content_charset=lambda: None)
        def __init__(self, body): self.body = body
        def geturl(self): return "https://www.cninfo.com.cn/report.pdf"
        def read(self, amount): return self.body[:amount]
        def __enter__(self): return self
        def __exit__(self, *_args): pass
    opener = lambda body: SimpleNamespace(open=lambda *_args, **_kwargs: Response(body))
    large = agent_sources.read_original_page("https://www.cninfo.com.cn/report.pdf", "ExampleCorp", "cninfo", opener=opener(b"x" * 2_000_001))
    assert large["status"] == "unsupported_source"
    broken = agent_sources.read_original_page("https://www.cninfo.com.cn/report.pdf", "ExampleCorp", "cninfo", opener=opener(b"%PDF-invalid"))
    assert broken["status"] == "read_failed"


def test_rate_limit_has_distinct_read_status(monkeypatch):
    import urllib.error
    monkeypatch.setattr(agent_sources, "validate_public_http_url", lambda *_args, **_kwargs: None)
    def reject(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://www.zhihu.com/p/1", 429, "Too Many Requests", {}, None)
    result = agent_sources.read_original_page("https://www.zhihu.com/p/1", "示例公司", "zhihu", opener=SimpleNamespace(open=reject))
    assert result["status"] == "rate_limited"


def test_old_job_evidence_is_not_reused_as_current_listing():
    from jobfindsme.research.agent_store import _fresh

    now = datetime.now(UTC)
    old = {"retrieved_at": (now - timedelta(days=2)).isoformat(),
           "context": {"research_topic": "job", "source_type": "public_web"}}
    recent = {**old, "retrieved_at": (now - timedelta(hours=2)).isoformat()}
    assert not _fresh(old, at=now)
    assert _fresh(recent, at=now)


def test_agent_endpoints_require_auth_and_do_not_cross_workspace(tmp_path):
    client = TestClient(create_app(token="secret", database_path=tmp_path / "api.db"))
    assert client.get("/v1/research-agent/conversations?workspace_id=x").status_code == 401
    workspace = client.get("/v1/bootstrap", headers={"Authorization": "Bearer secret"}).json()["workspaces"][0]["workspace_id"]
    headers = {"Authorization": "Bearer secret"}
    assert client.put("/v1/research-agent/conversations", headers=headers, json={"workspace_id": workspace, "id": "c1", "turns": [{"role": "user", "text": "研究示例公司"}]}).status_code == 200
    assert len(client.get("/v1/research-agent/conversations", headers=headers, params={"workspace_id": workspace}).json()) == 1
    assert client.get("/v1/research-agent/conversations", headers=headers, params={"workspace_id": "elsewhere"}).status_code == 404
