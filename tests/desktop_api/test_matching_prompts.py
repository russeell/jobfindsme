"""Protocol simulation: no paid/network model request is made."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_job_snapshots import _job

from jobfindsme.desktop_api import create_app
from jobfindsme.desktop_jobs import DesktopJobFilters, DesktopJobService
from jobfindsme.desktop_rules import DEFAULT_WEIGHTS
from jobfindsme.importing.repository import JobRepository
from jobfindsme.matching_prompts import MatchingPromptService
from jobfindsme.models import (
    CancellationToken,
    ModelConnectionRepository,
    ModelGateway,
    ModelProtocol,
)
from jobfindsme.models.gateway import ModelCancelledError, TransportResponse
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.scheduler import LocalScheduler
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


class SimulatedTransport:
    def __init__(self):
        self.prompts = []
        self.invalid = False

    def post(self, *, payload, cancellation, **kwargs):
        cancellation.raise_if_cancelled()
        prompt = payload["messages"][-1]["content"]
        self.prompts.append(prompt)
        data = json.loads(prompt.split("\n", 1)[1])
        candidates = data["candidates"]
        reverse = "优先最后" in data["instructions"]
        items = [
            {
                "job_id": c["job_id"],
                "score": float(i * 10 if reverse else 100 - i * 10),
                "evidence": [
                    {
                        "resume_quote": "编造证据" if self.invalid else "Python",
                        "jd_quote": "Python",
                    }
                ],
                "unknowns": ["学历未知"],
            }
            for i, c in enumerate(candidates)
        ]
        return TransportResponse(
            status=200,
            payload={
                "choices": [{"message": {"content": json.dumps({"items": items})}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 30},
            },
        )


def setup(tmp_path):
    database = Database(tmp_path / "matching.db")
    database.migrate()
    ws = WorkspaceService(database).create().workspace_id
    jobs = JobRepository(database)
    service = DesktopJobService(database, jobs)
    profiles = ResumeProfileService(database)
    source = tmp_path / "synthetic.md"
    source.write_text(
        "# Skills\nPython synthetic@example.invalid\n# Projects\n实现 Python 服务",
        encoding="utf8",
    )
    draft = profiles.import_resume(workspace_id=ws, source_path=source)
    profiles.confirm_profile(
        workspace_id=ws,
        profile_id=draft.profile_id,
        accepted_fact_ids=[f.fact_id for f in draft.facts],
    )
    resume = profiles.current_version(workspace_id=ws)
    values = [_job(i, description="Python 开发工程师，岗位原文。") for i in range(25)]
    for j in values:
        jobs.upsert(ws, j)
    connections = ModelConnectionRepository(database)
    conn = connections.save(
        provider="SIMULATED",
        protocol=ModelProtocol.OPENAI_COMPATIBLE,
        endpoint="http://127.0.0.1:18888/v1",
        model_id="synthetic-model",
        auth_mode="none",
    )
    with database.connect() as db:
        db.execute(
            "UPDATE model_connections SET status='verified' WHERE connection_id=?",
            (conn.connection_id,),
        )
    transport = SimulatedTransport()
    matching = MatchingPromptService(
        database, service, connections, ModelGateway(transport)
    )
    return database, ws, service, resume, values, conn, transport, matching


def save(matching, ws, conn, prompt):
    return matching.save(
        ws,
        name="合成协议验收",
        prompt=prompt,
        template_id="balanced",
        mode="model",
        connection_id=conn.connection_id,
        candidate_limit=3,
        weights=DEFAULT_WEIGHTS,
    )


def test_prompt_changes_order_bounded_pool_and_preserves_history(tmp_path):
    database, ws, service, resume, jobs, conn, transport, matching = setup(tmp_path)
    legacy = service.create_snapshot(
        workspace_id=ws,
        intent="Python",
        job_ids=[j.job_id for j in jobs],
        resume_version=resume,
        filters=DesktopJobFilters(),
    )
    original = service.page(workspace_id=ws, run_id=legacy, page=1, page_size=50)
    rule = save(matching, ws, conn, "优先最后，synthetic@example.invalid")
    base = service.create_snapshot(
        workspace_id=ws,
        intent="Python",
        job_ids=[j.job_id for j in jobs],
        resume_version=resume,
        filters=DesktopJobFilters(),
    )
    result = matching.rerank(ws, base, api_key="", cancellation=CancellationToken())
    page = service.page(
        workspace_id=ws, run_id=result["page"]["run_id"], page=1, page_size=50
    )
    assert page["rule_version_id"] == rule["rule_version_id"]

    def ids(p):
        return [i["job"]["job_id"] for i in p["items"]]

    assert ids(page)[:3] == list(reversed(ids(original)[:3]))
    assert ids(page)[3:] == ids(original)[3:]
    assert page["rerank"]["candidate_count"] == 3
    assert "synthetic@example.invalid" not in transport.prompts[0]
    assert "不可信资料" in transport.prompts[0]
    frozen = json.dumps(page, sort_keys=True)
    save(matching, ws, conn, "优先最前")
    other = service.create_snapshot(
        workspace_id=ws,
        intent="Python",
        job_ids=[j.job_id for j in jobs],
        resume_version=resume,
        filters=DesktopJobFilters(),
    )
    other_page = matching.rerank(
        ws, other, api_key="", cancellation=CancellationToken()
    )["page"]
    assert ids(other_page)[:3] == ids(original)[:3]
    assert (
        json.dumps(
            service.page(workspace_id=ws, run_id=page["run_id"], page=1, page_size=50),
            sort_keys=True,
        )
        == frozen
    )
    assert (
        service.page(workspace_id=ws, run_id=legacy, page=1, page_size=50) == original
    )
    assert (
        service.page(workspace_id=ws, run_id=base, page=1, page_size=50)["rerank"]
        is None
    )


def test_rejects_invented_quotes_cancel_and_no_resume(tmp_path):
    db, ws, service, resume, jobs, conn, transport, matching = setup(tmp_path)
    save(matching, ws, conn, "优先最后")

    def run(resume):
        return service.create_snapshot(
            workspace_id=ws,
            intent="Python",
            job_ids=[j.job_id for j in jobs],
            resume_version=resume,
            filters=DesktopJobFilters(),
        )

    base = run(resume)
    transport.invalid = True
    with pytest.raises(ValueError, match="引用"):
        matching.rerank(ws, base, api_key="", cancellation=CancellationToken())
    token = CancellationToken()
    token.cancel()
    with pytest.raises(ModelCancelledError):
        matching.rerank(ws, base, api_key="", cancellation=token)
    count = len(transport.prompts)
    assert (
        matching.rerank(ws, run(None), api_key="", cancellation=CancellationToken())[
            "status"
        ]
        == "skipped"
    )
    assert len(transport.prompts) == count
    assert (
        service.page(workspace_id=ws, run_id=base, page=1, page_size=10)["rerank"]
        is None
    )
    other = WorkspaceService(db).create().workspace_id
    with pytest.raises(ValueError):
        matching.input_for_run(other, base)


def test_api_and_new_scheduled_tasks_freeze_active_prompt(tmp_path):
    db, ws, service, resume, jobs, conn, transport, matching = setup(tmp_path)
    rule = save(matching, ws, conn, "优先最后")
    client = TestClient(
        create_app(
            token="secret",
            database_path=tmp_path / "matching.db",
            model_gateway_override=ModelGateway(transport),
        )
    )
    headers = {"Authorization": "Bearer secret"}
    assert (
        client.get("/v1/matching-rules", params={"workspace_id": ws}).status_code == 401
    )
    task = client.post(
        "/v1/tasks",
        headers=headers,
        json={
            "workspace_id": ws,
            "name": "合成任务",
            "intent": "Python",
            "source_ids": ["liepin"],
            "frequency": "interval",
            "timezone": "Asia/Shanghai",
            "interval_minutes": 60,
        },
    ).json()
    assert task["rule_version_id"] == rule["rule_version_id"]
    saved = save(matching, ws, conn, "优先最前")
    assert (
        LocalScheduler(db).get_task(task["task_id"])["rule_version_id"]
        == rule["rule_version_id"]
    )
    assert service.ensure_rule_version(ws) == saved["rule_version_id"]
    trial = client.post(
        "/v1/matching-trials",
        headers=headers,
        json={
            "workspace_id": ws,
            "job_id": jobs[0].job_id,
            "rule_version_id": rule["rule_version_id"],
        },
    ).json()
    result = client.post(
        "/v1/matching-rerank",
        headers=headers,
        json={
            "workspace_id": ws,
            "run_id": trial["run_id"],
            "request_id": "test-request-123456",
        },
    ).json()
    assert result["status"] == "complete"
    assert "优先最后" in transport.prompts[-1]


def test_scheduled_execution_uses_frozen_prompt_and_reports_missing_key(tmp_path):
    from datetime import timedelta

    from jobfindsme.connectors import RawJobRecord
    from jobfindsme.contracts import SourceKind
    from jobfindsme.desktop_search import SourcePage

    db, ws, service, resume, jobs, conn, transport, matching = setup(tmp_path)
    old = save(matching, ws, conn, "优先最后")
    now = [datetime(2026, 9, 19, tzinfo=UTC)]

    class Adapter:
        def fetch_page(self, cursor):
            return SourcePage(
                records=tuple(
                    RawJobRecord(
                        source_kind=SourceKind.CAREER_SITE,
                        source_name="猎聘",
                        source_url=f"https://www.liepin.com/job/{i}",
                        external_id=str(i),
                        payload={
                            "title": f"合成岗位{i}",
                            "company": "合成公司",
                            "description": "Python 工程师",
                        },
                    )
                    for i in range(3)
                )
            )

    app = create_app(
        token="secret",
        database_path=tmp_path / "matching.db",
        model_gateway_override=ModelGateway(transport),
        source_adapter_factory_override=lambda *_: Adapter(),
        scheduler_clock_override=lambda: now[0],
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer secret"}
    task = client.post(
        "/v1/tasks",
        headers=headers,
        json={
            "workspace_id": ws,
            "name": "冻结提示词任务",
            "intent": "Python",
            "source_ids": ["liepin"],
            "frequency": "interval",
            "timezone": "Asia/Shanghai",
            "interval_minutes": 60,
        },
    ).json()
    save(matching, ws, conn, "优先最前")
    now[0] += timedelta(hours=2)
    response = client.post(
        "/v1/tasks/run-due",
        headers=headers,
        json={"matching_keys_by_task": {task["task_id"]: ""}},
    )
    assert response.status_code == 200, response.text
    assert transport.prompts and "优先最后" in transport.prompts[-1]
    with db.connect() as sql:
        row = sql.execute(
            "SELECT search_run_id FROM desktop_task_runs WHERE task_id=?",
            (task["task_id"],),
        ).fetchone()
    page = service.page(workspace_id=ws, run_id=row[0], page=1, page_size=10)
    assert (
        page["rule_version_id"] == old["rule_version_id"]
        and page["rerank"]["candidate_count"] == 3
    )
    now[0] += timedelta(hours=2)
    count = len(transport.prompts)
    client.post("/v1/tasks/run-due", headers=headers, json={})
    assert len(transport.prompts) == count
    assert "模型重排失败" in LocalScheduler(db).get_task(task["task_id"])["last_error"]


def test_cancel_before_registration_and_no_resume_trial(tmp_path):
    db, ws, service, resume, jobs, conn, transport, matching = setup(tmp_path)
    rule = save(matching, ws, conn, "优先最后")
    app = create_app(
        token="secret",
        database_path=tmp_path / "matching.db",
        model_gateway_override=ModelGateway(transport),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer secret"}
    run = service.create_snapshot(
        workspace_id=ws,
        intent="Python",
        job_ids=[j.job_id for j in jobs],
        resume_version=resume,
        filters=DesktopJobFilters(),
    )
    client.post(
        "/v1/matching-cancel",
        headers=headers,
        params={"workspace_id": ws, "request_id": "early-cancel-123456"},
    )
    result = client.post(
        "/v1/matching-rerank",
        headers=headers,
        json={"workspace_id": ws, "run_id": run, "request_id": "early-cancel-123456"},
    ).json()
    assert result["status"] == "cancelled" and not transport.prompts
    with db.connect() as sql:
        sql.execute(
            "UPDATE resume_versions SET is_current=0 WHERE workspace_id=?", (ws,)
        )
    trial = client.post(
        "/v1/matching-trials",
        headers=headers,
        json={
            "workspace_id": ws,
            "job_id": jobs[0].job_id,
            "rule_version_id": rule["rule_version_id"],
        },
    )
    assert trial.status_code == 400 and "尚未评分" in trial.text
