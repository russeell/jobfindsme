from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jobfindsme.desktop_api import create_app
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


def test_agent_endpoints_require_auth_and_do_not_cross_workspace(tmp_path):
    client = TestClient(create_app(token="secret", database_path=tmp_path / "api.db"))
    assert client.get("/v1/research-agent/conversations?workspace_id=x").status_code == 401
    workspace = client.get("/v1/bootstrap", headers={"Authorization": "Bearer secret"}).json()["workspaces"][0]["workspace_id"]
    headers = {"Authorization": "Bearer secret"}
    assert client.put("/v1/research-agent/conversations", headers=headers, json={"workspace_id": workspace, "id": "c1", "turns": [{"role": "user", "text": "研究示例公司"}]}).status_code == 200
    assert len(client.get("/v1/research-agent/conversations", headers=headers, params={"workspace_id": workspace}).json()) == 1
    assert client.get("/v1/research-agent/conversations", headers=headers, params={"workspace_id": "elsewhere"}).status_code == 404
