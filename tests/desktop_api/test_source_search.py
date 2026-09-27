from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jobfindsme.connectors import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.desktop_api.app import create_app
from jobfindsme.desktop_api.source_search_runs import source_run_outcome
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search.desktop import (
    BudgetedSourceExecutor,
    DesktopSearchService,
    SearchPreflightError,
    SourceExecutionResult,
    SourcePage,
    build_search_keywords,
    connector_adapter_for,
)
from jobfindsme.sources.desktop import DesktopSourceService, SourceGateError
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def _confirmed_resume(tmp_path: Path):
    database = Database(tmp_path / "desktop.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    profiles = ResumeProfileService(database)
    source = tmp_path / "resume.md"
    source.write_text(
        "姓名：张三\n电话：13800138000\n# Skills\nPython、RAG、SQL\n"
        "# Projects\n使用 FastAPI 实现本地求职工具",
        encoding="utf-8",
    )
    draft = profiles.import_resume(
        workspace_id=workspace.workspace_id,
        source_path=source,
    )
    profiles.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=draft.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in draft.facts],
    )
    return database, workspace, profiles


def test_source_catalog_separates_login_and_capability_gates(tmp_path) -> None:
    sources = DesktopSourceService(Database(tmp_path / "desktop.db"))
    platforms = sources.list(source_type="platform")
    companies = sources.list(source_type="company")

    assert len(platforms) == 4
    assert companies == []
    assert {item.source_id for item in sources.list()} == {
        "boss",
        "liepin",
        "zhilian",
        "wuyou",
    }
    with pytest.raises(LookupError):
        sources.get("company_01")
    liepin = sources.require_live_search("liepin")
    assert liepin.session_status == "anonymous"
    assert "生产 .app 快照 92 条" in liepin.notes
    assert "桌面快照页数不代表来源全量分页" in liepin.notes
    for source_id in ("boss", "zhilian", "wuyou"):
        with pytest.raises(SourceGateError, match="verified login"):
            sources.require_live_search(source_id)
    with pytest.raises(SourceGateError, match="verified session and list"):
        sources.record_verification(
            source_id="boss",
            session_status="unverified",
            list_status="verified",
            detail_status="unverified",
            fields_status="partial",
            pagination_status="unverified",
            enabled=True,
            notes="offline fixture",
        )


def test_legacy_company_capability_is_preserved_but_retired(tmp_path) -> None:
    database = Database(tmp_path / "legacy.db")
    DesktopSourceService(database)
    with database.connect() as connection:
        connection.execute(
            """INSERT INTO desktop_source_capabilities
            (source_id, source_type, name, login_required, session_status,
             list_status, detail_status, fields_status, pagination_status,
             enabled, last_verified_at, notes)
            VALUES ('company_01', 'company', '腾讯', 0, 'anonymous',
                    'verified', 'verified', 'partial', 'partial', 1, NULL,
                    '旧来源记录')"""
        )
    sources = DesktopSourceService(database)
    assert {item.source_id for item in sources.list()} == {
        "boss",
        "liepin",
        "zhilian",
        "wuyou",
    }
    historical = sources.get("company_01")
    assert historical.notes == "旧来源记录"
    assert not historical.enabled
    with pytest.raises(SourceGateError):
        sources.require_live_search("company_01")


def test_explicit_query_stays_remote_query_and_resume_is_local_matching_input(
    tmp_path,
) -> None:
    database, workspace, profiles = _confirmed_resume(tmp_path)
    service = DesktopSearchService(
        profiles=profiles,
        sources=DesktopSourceService(database),
    )

    preflight = service.preflight(
        workspace_id=workspace.workspace_id,
        intent="AI 应用工程师",
        source_ids=["boss", "liepin", "zhilian", "wuyou"],
    )

    assert preflight.resume_version_id is not None
    assert preflight.keywords == ("AI 应用工程师",)
    assert "张三" not in " ".join(preflight.keywords)
    assert "13800138000" not in " ".join(preflight.keywords)
    assert preflight.allowed_source_ids == ("liepin",)
    assert set(preflight.blocked_sources) == {"boss", "zhilian", "wuyou"}


def test_confirmed_resume_can_search_without_manual_keywords_then_clear(
    tmp_path,
) -> None:
    database, workspace, profiles = _confirmed_resume(tmp_path)
    service = DesktopSearchService(
        profiles=profiles, sources=DesktopSourceService(database)
    )
    generated = service.preflight(
        workspace_id=workspace.workspace_id, intent="", source_ids=["liepin"]
    )
    assert generated.resume_version_id
    assert len(generated.keywords) == 1
    assert "Python" in " ".join(generated.keywords)
    assert "张三" not in " ".join(generated.keywords)
    assert "13800138000" not in " ".join(generated.keywords)
    manual = service.preflight(
        workspace_id=workspace.workspace_id, intent="数据工程师", source_ids=["liepin"]
    )
    assert "数据工程师" in manual.keywords[0]
    profiles.clear_current(workspace_id=workspace.workspace_id)
    with pytest.raises(SearchPreflightError, match="enter a job keyword"):
        service.preflight(
            workspace_id=workspace.workspace_id, intent="", source_ids=["liepin"]
        )
    assert service.preflight(
        workspace_id=workspace.workspace_id, intent="数据工程师", source_ids=["liepin"]
    ).keywords == ("数据工程师",)


def test_pending_resume_blocks_search_instead_of_falling_back(tmp_path) -> None:
    database = Database(tmp_path / "desktop.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    profiles = ResumeProfileService(database)
    source = tmp_path / "resume.txt"
    source.write_text("Python", encoding="utf-8")
    profiles.import_resume(workspace_id=workspace.workspace_id, source_path=source)
    service = DesktopSearchService(
        profiles=profiles,
        sources=DesktopSourceService(database),
    )

    with pytest.raises(SearchPreflightError, match="confirmed or abandoned"):
        service.preflight(
            workspace_id=workspace.workspace_id,
            intent="后端工程师",
            source_ids=["liepin"],
        )


def test_budgeted_executor_reports_continuation_without_claiming_full_coverage() -> (
    None
):
    class Adapter:
        def fetch_page(self, cursor):
            number = 1 if cursor is None else int(cursor)
            record = RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name="fixture",
                source_url="https://example.com/jobs",
                external_id=str(number),
                payload={"title": f"岗位 {number}"},
            )
            return SourcePage(records=(record,), next_cursor=str(number + 1))

    result = BudgetedSourceExecutor().run(
        Adapter(),
        max_pages=2,
        time_budget_seconds=10,
    )

    assert result.pages_fetched == 2
    assert result.coverage_status == "partial"
    assert result.can_continue is True
    assert result.next_cursor == "3"
    assert result.stop_reason == "page_budget"


def test_source_run_does_not_call_invalid_rows_partial_success() -> None:
    result = SourceExecutionResult(
        records=(),
        pages_fetched=1,
        elapsed_seconds=1,
        coverage_status="partial",
        can_continue=False,
        next_cursor=None,
        stop_reason="source_contract_error",
    )
    outcome = source_run_outcome(
        result,
        collection=None,
        browser_error="risk_control:verification required",
        normalization_errors=1,
        valid_count=0,
    )
    assert outcome.status == "failed"
    assert outcome.coverage_status == "failed"
    assert outcome.stop_reason == "risk_control"


def test_production_connector_factory_reuses_liepin_without_legacy_cdp() -> None:
    assert (
        connector_adapter_for(
            source_id="liepin", keyword="AI 工程师 Python", city="上海"
        ).connector.__class__.__name__
        == "LiepinPureHttpConnector"
    )
    with pytest.raises(SourceGateError, match="Electron session bridge"):
        connector_adapter_for(source_id="boss", keyword="AI", city="上海")


def test_no_resume_keywords_use_only_explicit_intent() -> None:
    assert build_search_keywords(intent="数据工程师", resume=None) == ("数据工程师",)
    resume = SimpleNamespace(
        version_id="resume_1",
        content={"skills": ["Python、RAG、SQL"], "experience": ["FastAPI 项目"]},
    )
    assert build_search_keywords(intent="AI 工程师", resume=resume) == ("AI 工程师",)
    assert build_search_keywords(intent="", resume=resume) == ("Python",)


def test_source_search_api_applies_backend_gates_before_adapter(tmp_path) -> None:
    database, workspace, _profiles = _confirmed_resume(tmp_path)
    called: list[str] = []

    class Adapter:
        def fetch_page(self, cursor):
            return SourcePage(
                records=(
                    RawJobRecord(
                        source_kind=SourceKind.CAREER_SITE,
                        source_name="猎聘",
                        source_url="https://www.liepin.com/zhaopin/",
                        external_id="job-1",
                        payload={"title": "AI 应用工程师", "company": "示例公司"},
                    ),
                )
            )

    def factory(source_id, keyword, city):
        called.append(source_id)
        assert "Python" in keyword
        return Adapter()

    app = create_app(
        token="test-secret",
        database_path=database.path,
        source_adapter_factory_override=factory,
    )
    response = TestClient(app).post(
        "/v1/source-searches",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "",
            "source_ids": ["boss", "liepin", "zhilian", "wuyou"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert called == ["liepin"]
    assert payload["jobs"][0]["external_id"] == "job-1"
    assert "Python" in " ".join(payload["keywords"])
    assert payload["result_page"]["total"] == 1
    with database.connect() as connection:
        snapshot = connection.execute(
            "SELECT intent FROM desktop_search_runs WHERE run_id=?",
            (payload["result_page"]["run_id"],),
        ).fetchone()
    assert snapshot["intent"] == payload["keywords"][0]
    assert set(payload["blocked_sources"]) == {"boss", "zhilian", "wuyou"}


def test_source_search_accepts_only_backend_gated_serialized_browser_pages(tmp_path):
    database, workspace, _profiles = _confirmed_resume(tmp_path)
    sources = DesktopSourceService(database)
    sources.record_verification(
        source_id="boss",
        session_status="verified",
        list_status="verified",
        detail_status="partial",
        fields_status="partial",
        pagination_status="partial",
        enabled=True,
        notes="fixture verified session",
    )

    def factory(*_args):
        raise AssertionError("serialized browser page must not call legacy connector")

    app = create_app(
        token="test-secret",
        database_path=database.path,
        source_adapter_factory_override=factory,
    )
    response = TestClient(app).post(
        "/v1/source-searches",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "AI 应用工程师",
            "source_ids": ["boss"],
            "browser_pages": {
                "boss": [
                    {
                        "records": [
                            {
                                "external_id": "boss-1",
                                "source_name": "BOSS直聘",
                                "source_url": "https://www.zhipin.com/web/geek/job",
                                "payload": {
                                    "title": "AI 应用工程师",
                                    "company": "示例公司",
                                    "description": "Python FastAPI",
                                    "url": "https://www.zhipin.com/job_detail/1.html",
                                    "apply_url": "https://www.zhipin.com/job_detail/1.html",
                                },
                            }
                        ],
                        "next_cursor": None,
                    }
                ]
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["jobs"][0]["external_id"] == "boss-1"


def test_runtime_login_failure_revokes_source_gate(tmp_path):
    database, _workspace, _profiles = _confirmed_resume(tmp_path)
    sources = DesktopSourceService(database)
    sources.record_verification(
        source_id="boss",
        session_status="verified",
        list_status="verified",
        detail_status="partial",
        fields_status="partial",
        pagination_status="partial",
        enabled=True,
        notes="fixture verified session",
    )
    app = create_app(token="test-secret", database_path=database.path)
    response = TestClient(app).post(
        "/v1/sources/boss/runtime-failure",
        headers={"Authorization": "Bearer test-secret"},
        json={"failure": "login_required", "notes": "登录状态已失效"},
    )
    assert response.status_code == 200
    assert response.json()["session_status"] == "expired"
    assert response.json()["live_search_enabled"] is False
    with pytest.raises(SourceGateError):
        sources.require_live_search("boss")


def test_boss_partial_collection_keeps_jobs_before_revoking_gate(tmp_path):
    database, workspace, _ = _confirmed_resume(tmp_path)
    sources = DesktopSourceService(database)
    sources.record_verification(
        source_id="boss",
        session_status="verified",
        list_status="verified",
        detail_status="partial",
        fields_status="partial",
        pagination_status="unverified",
        enabled=True,
        notes="fixture",
    )
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    response = client.post(
        "/v1/source-searches",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "Python",
            "source_ids": ["boss"],
            "browser_pages": {
                "boss": [
                    {
                        "records": [
                            {
                                "external_id": "boss-partial",
                                "source_name": "BOSS直聘",
                                "source_url": "https://www.zhipin.com/web/geek/jobs",
                                "payload": {
                                    "title": "Python工程师",
                                    "company": "样例",
                                    "description": "",
                                    "url": "https://www.zhipin.com/job_detail/test.html",
                                },
                            }
                        ],
                        "next_cursor": None,
                        "collection": {
                            "batches": 2,
                            "elapsed_seconds": 7,
                            "stop_reason": "risk_control",
                            "cursor": None,
                            "complete": False,
                            "failure": "risk_control",
                        },
                    }
                ]
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["jobs"]) == 1
    assert body["source_runs"][0]["status"] == "partial"
    assert body["source_runs"][0]["coverage_status"] == "partial"
    assert body["source_runs"][0]["elapsed_seconds"] == 7
    assert body["result_page"]["total"] == 1
    assert not sources.get("boss").live_search_enabled


def test_source_batches_append_without_reordering_or_rescoring_previous_jobs(tmp_path):
    database, workspace, _ = _confirmed_resume(tmp_path)
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    headers = {"Authorization": "Bearer test-secret"}

    def batch(external_id, existing_run_id=None):
        record = {
            "external_id": external_id,
            "source_name": "猎聘",
            "source_url": "https://www.liepin.com/",
            "payload": {
                "title": "Python工程师",
                "company": f"样例{external_id}",
                "description": "Python",
                "url": f"https://www.liepin.com/job/{external_id}.shtml",
            },
        }
        response = client.post(
            "/v1/source-searches",
            headers=headers,
            json={
                "workspace_id": workspace.workspace_id,
                "intent": "Python",
                "source_ids": ["liepin"],
                "max_pages": 1,
                "existing_run_id": existing_run_id,
                "browser_pages": {
                    "liepin": [{"records": [record], "next_cursor": None}]
                },
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["result_page"]

    first = batch("one")
    repeated = batch("one", first["run_id"])
    appended = batch("two", first["run_id"])
    assert repeated["total"] == 1
    assert appended["run_id"] == first["run_id"]
    assert appended["total"] == 2
    assert appended["items"][0] == first["items"][0]
    missing = client.post(
        "/v1/source-searches",
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "Python",
            "source_ids": ["liepin"],
            "existing_run_id": "search_missing",
            "browser_pages": {"liepin": [{"records": [], "next_cursor": None}]},
        },
    )
    assert missing.status_code == 404


def test_salary_yuan_input_is_not_a_backend_k_value(tmp_path):
    database, workspace, _ = _confirmed_resume(tmp_path)
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    base = {
        "workspace_id": workspace.workspace_id,
        "intent": "agent",
        "source_ids": ["liepin"],
    }
    headers = {"Authorization": "Bearer test-secret"}
    invalid = client.post(
        "/v1/search-preflight",
        headers=headers,
        json={**base, "filters": {"salary_min_k": 20000}},
    )
    assert invalid.status_code == 422
    valid = client.post(
        "/v1/search-preflight",
        headers=headers,
        json={**base, "filters": {"salary_min_k": 20}},
    )
    assert valid.status_code == 200


def test_agent_two_sources_and_20_to_50k_filter_keep_overlap_and_unknown(tmp_path):
    database, workspace, _ = _confirmed_resume(tmp_path)
    DesktopSourceService(database).record_verification(
        source_id="zhilian",
        session_status="verified",
        list_status="verified",
        detail_status="unverified",
        fields_status="partial",
        pagination_status="unverified",
        enabled=True,
        notes="synthetic test platform",
    )
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    headers = {"Authorization": "Bearer test-secret"}

    def record(source_name, external_id, company, salary=None):
        return {
            "external_id": external_id,
            "source_name": source_name,
            "source_url": "https://www.liepin.com/"
            if source_name == "猎聘"
            else "https://www.zhaopin.com/",
            "payload": {
                "title": "Agent 工程师",
                "company": company,
                "description": "Agent 开发",
                "url": f"https://example.org/jobs/{external_id}",
                **({"raw_salary_text": salary} if salary else {}),
            },
        }

    response = client.post(
        "/v1/source-searches",
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "agent",
            "source_ids": ["liepin", "zhilian"],
            "max_pages": 1,
            "filters": {
                "salary_min_k": 20,
                "salary_max_k": 50,
                "salary_mode": "overlap",
                "unknown_policy": "include",
            },
            "browser_pages": {
                "liepin": [
                    {
                        "records": [
                            record("猎聘", "overlap", "样例一", "15-25K"),
                            record("猎聘", "outside", "样例二", "10-15K"),
                        ],
                        "next_cursor": None,
                    }
                ],
                "zhilian": [
                    {
                        "records": [record("智联招聘", "unknown", "样例三")],
                        "next_cursor": None,
                    }
                ],
            },
        },
    )
    assert response.status_code == 200, response.text
    jobs = response.json()["result_page"]["items"]
    assert {item["job"]["company"] for item in jobs} == {"样例一", "样例三"}


def test_refilter_restores_all_collected_candidates_without_network(tmp_path):
    database, workspace, _ = _confirmed_resume(tmp_path)
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    headers = {"Authorization": "Bearer test-secret"}
    records = [
        {
            "external_id": f"refilter-{i}",
            "source_name": "猎聘",
            "source_url": "https://www.liepin.com/",
            "payload": {
                "title": "Python工程师",
                "company": f"样例{i}",
                "location": city,
                "description": "Python",
                "url": f"https://www.liepin.com/job/{i}.shtml",
            },
        }
        for i, city in enumerate(["上海", "北京"])
    ]
    response = client.post(
        "/v1/source-searches",
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "Python",
            "source_ids": ["liepin"],
            "filters": {"cities": ["上海"], "unknown_policy": "exclude"},
            "browser_pages": {"liepin": [{"records": records, "next_cursor": None}]},
        },
    )
    assert response.status_code == 200, response.text
    run = response.json()["result_page"]
    assert run["total"] == 1
    reset = client.post(
        f"/v1/search-runs/{run['run_id']}/refilter",
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "filters": {
                "read": "any",
                "unknown_policy": "include",
                "salary_mode": "overlap",
            },
            "page_size": 10,
        },
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["total"] == 2
    assert reset.json()["resume_version_id"] == run["resume_version_id"]
    assert reset.json()["rule_version_id"] == run["rule_version_id"]

    import json

    with database.connect() as connection:
        row = connection.execute(
            "SELECT scores_json FROM desktop_search_runs WHERE run_id=?",
            (run["run_id"],),
        ).fetchone()
        scores = json.loads(row["scores_json"])
        job_id = next(iter(scores))
        scores[job_id]["score"] = 99
        scores[job_id]["model_match"] = {"score": 99, "evidence": [], "unknowns": []}
        connection.execute(
            "UPDATE desktop_search_runs SET scores_json=?,rerank_json=? WHERE run_id=?",
            (
                json.dumps(scores),
                json.dumps({"status": "complete", "total": 1}),
                run["run_id"],
            ),
        )
    preserved = client.post(
        f"/v1/search-runs/{run['run_id']}/refilter",
        headers=headers,
        json={"workspace_id": workspace.workspace_id, "filters": {}, "page_size": 10},
    )
    assert preserved.status_code == 200, preserved.text
    assert preserved.json()["total"] == 2
    assert preserved.json()["items"][0]["score"] == 99
    assert preserved.json()["items"][0]["job"]["job_id"] == job_id


def test_bad_source_record_does_not_drop_other_records(tmp_path, monkeypatch):
    import importlib

    module = importlib.import_module("jobfindsme.desktop_api.app")
    original = module.normalize_job

    def normalize(record):
        if record.external_id == "bad":
            raise ValueError("malformed fixture")
        return original(record)

    monkeypatch.setattr(module, "normalize_job", normalize)
    database, workspace, _ = _confirmed_resume(tmp_path)
    DesktopSourceService(database).record_verification(
        source_id="zhilian",
        session_status="verified",
        list_status="verified",
        detail_status="unverified",
        fields_status="partial",
        pagination_status="unverified",
        enabled=True,
        notes="synthetic test platform",
    )
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    records = [
        {
            "external_id": key,
            "source_name": "猎聘",
            "source_url": "https://www.liepin.com/",
            "payload": {
                "title": "Python",
                "company": "样例",
                "description": "Python",
                "url": f"https://www.liepin.com/job/{key}.shtml",
            },
        }
        for key in ["bad", "good"]
    ]
    response = client.post(
        "/v1/source-searches",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "Python",
            "source_ids": ["liepin", "zhilian"],
            "browser_errors": {"zhilian": "fixture source failed"},
            "browser_pages": {"liepin": [{"records": records, "next_cursor": None}]},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["result_page"]["total"] == 1
    assert [r["status"] for r in response.json()["source_runs"]] == [
        "partial",
        "failed",
    ]


def test_full_jd_keeps_plaintext_and_original_fetch_provenance():
    from jobfindsme.importing.normalizer import normalize_job

    description = "职责：\n维护 C++ template<T> 服务。\n\n要求：\nPython 与 SQL。"
    job = normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="BOSS直聘",
            source_url="https://www.zhipin.com/web/geek/jobs",
            external_id="fixture",
            payload={
                "title": "Python工程师",
                "company": "样例",
                "description": description,
                "description_is_plaintext": True,
                "detail_level": "detail_page",
                "description_source_url": "https://www.zhipin.com/job_detail/test.html",
                "description_fetched_at": "2026-09-19T00:00:00+00:00",
            },
        )
    )
    assert job.description == description
    assert job.source.description_source_url.endswith("/test.html")
    assert job.source.description_fetched_at.isoformat() == "2026-09-19T00:00:00+00:00"


def test_explicit_subset_and_empty_source_selection_never_expand(tmp_path):
    database, workspace, _ = _confirmed_resume(tmp_path)
    called = []

    class Adapter:
        def fetch_page(self, cursor):
            return SourcePage(records=())

    def factory(source_id, keyword, city):
        called.append(source_id)
        return Adapter()

    client = TestClient(
        create_app(
            token="fixture",
            database_path=database.path,
            source_adapter_factory_override=factory,
        )
    )
    for requested, expected in [
        ([], []),
        (["company_01"], []),
        (["boss", "liepin"], ["liepin"]),
    ]:
        called.clear()
        response = client.post(
            "/v1/source-searches",
            headers={"Authorization": "Bearer fixture"},
            json={
                "workspace_id": workspace.workspace_id,
                "intent": "Python",
                "source_ids": requested,
            },
        )
        assert response.status_code == 200
        assert called == expected


def test_public_page_bridge_caches_and_keeps_partial_on_failure(tmp_path):
    calls = []

    class Adapter:
        def fetch_page(self, cursor):
            calls.append(cursor)
            if cursor is not None:
                raise RuntimeError("second page failed")
            return SourcePage(records=(), next_cursor="2")

    client = TestClient(
        create_app(
            token="test-secret",
            database_path=tmp_path / "db",
            source_adapter_factory_override=lambda *_: Adapter(),
        )
    )
    headers = {"Authorization": "Bearer test-secret"}
    body = {"keyword": "Python", "max_pages": 2}
    assert client.post("/v1/sources/liepin/public-pages", json=body).status_code == 401
    first = client.post("/v1/sources/liepin/public-pages", json=body, headers=headers)
    assert first.status_code == 200
    assert first.json()[0]["collection"]["complete"] is False
    assert first.json()[0]["next_cursor"] is None
    assert (
        client.post(
            "/v1/sources/liepin/public-pages", json=body, headers=headers
        ).json()
        == first.json()
    )
    assert calls == [None, "2"]
    assert (
        client.post(
            "/v1/sources/boss/public-pages", json=body, headers=headers
        ).status_code
        == 409
    )


def test_public_page_continuation_uses_returned_cursor(tmp_path):
    calls = []

    class Adapter:
        def fetch_page(self, cursor):
            calls.append(cursor)
            return SourcePage(records=(), next_cursor="2" if cursor is None else None)

    client = TestClient(
        create_app(
            token="test-secret",
            database_path=tmp_path / "db",
            source_adapter_factory_override=lambda *_: Adapter(),
        )
    )
    headers = {"Authorization": "Bearer test-secret"}
    endpoint = "/v1/sources/liepin/public-pages"
    first = client.post(
        endpoint, headers=headers, json={"keyword": "agent", "max_pages": 1}
    )
    assert first.status_code == 200
    assert first.json()[0]["next_cursor"] == "2"
    second = client.post(
        endpoint,
        headers=headers,
        json={"keyword": "agent", "max_pages": 1, "cursor": "2"},
    )
    assert second.status_code == 200
    assert calls == [None, "2"]


def test_public_page_bridge_force_refresh_bypasses_success_cache(tmp_path):
    calls = []

    class Adapter:
        def fetch_page(self, cursor):
            calls.append(cursor)
            return SourcePage(records=(), next_cursor=None)

    client = TestClient(
        create_app(
            token="fixture",
            database_path=tmp_path / "db",
            source_adapter_factory_override=lambda *_: Adapter(),
        )
    )
    endpoint = "/v1/sources/liepin/public-pages"
    headers = {"Authorization": "Bearer fixture"}
    body = {"keyword": "Python", "max_pages": 1}
    for request in (body, body, {**body, "force_refresh": True}):
        assert client.post(endpoint, json=request, headers=headers).status_code == 200
    assert calls == [None, None]


@pytest.mark.parametrize(
    "failure",
    [
        "cancelled:stop",
        "login_required:expired",
        "risk_control:captcha",
        "source_contract_error:page 2",
    ],
)
def test_source_search_keeps_valid_first_page_after_later_failure(tmp_path, failure):
    database, workspace, _profiles = _confirmed_resume(tmp_path)
    client = TestClient(create_app(token="test-secret", database_path=database.path))
    response = client.post(
        "/v1/source-searches",
        headers={"Authorization": "Bearer test-secret"},
        json={
            "workspace_id": workspace.workspace_id,
            "intent": "Python",
            "source_ids": ["liepin"],
            "browser_errors": {"liepin": failure},
            "browser_pages": {
                "liepin": [
                    {
                        "records": [
                            {
                                "external_id": "good",
                                "source_name": "猎聘",
                                "source_url": "https://www.liepin.com/",
                                "payload": {
                                    "title": "Python",
                                    "company": "样例",
                                    "description": "Python",
                                    "url": "https://www.liepin.com/job/good.shtml",
                                },
                            },
                            {
                                "external_id": "bad",
                                "source_name": "猎聘",
                                "source_url": "https://www.liepin.com/",
                                "payload": {
                                    "title": "",
                                    "company": "样例",
                                    "description": "",
                                    "url": "https://www.liepin.com/job/bad.shtml",
                                },
                            },
                        ],
                        "next_cursor": "2",
                    }
                ]
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [job["external_id"] for job in payload["jobs"]] == ["good"]
    run = payload["source_runs"][0]
    assert run["status"] == "partial"
    assert run["pages_fetched"] == 1
    assert run["error"] == failure
    assert run["can_continue"] is False
