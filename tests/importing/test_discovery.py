from __future__ import annotations

import json

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.core import JobFindsMeCore
from jobfindsme.importing import DiscoverySource, JobDiscoveryService


class FakeTransport:
    def get(self, url: str) -> bytes:
        assert "boards-api.greenhouse.io" in url
        return json.dumps(
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "AI应用工程师",
                        "location": {"name": "杭州"},
                        "content": "Python RAG Agent",
                        "absolute_url": "https://example.com/jobs/1",
                    }
                ]
            }
        ).encode()


def test_search_jobs_discovers_explicit_source_before_matching(tmp_path) -> None:
    core = JobFindsMeCore(tmp_path / "discover.db")
    core.discovery = JobDiscoveryService(
        core.job_imports,
        transport=FakeTransport(),
    )
    workspace = core.create_workspace("discover")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )

    matches = core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        sources=(
            DiscoverySource(
                kind="greenhouse",
                source_name="公开 ATS",
                board_token="example",
            ),
        ),
    )

    assert [item.job.external_id for item in matches] == ["1"]


def test_ashby_source_uses_public_board_name(tmp_path) -> None:
    class AshbyTransport:
        def get(self, url: str) -> bytes:
            assert url.endswith("example?includeCompensation=true")
            return json.dumps(
                {
                    "apiVersion": "1",
                    "jobs": [
                        {
                            "title": "RAG 工程师",
                            "location": "上海",
                            "descriptionPlain": "Python RAG Agent",
                            "publishedAt": "2026-07-20T08:00:00+00:00",
                            "jobUrl": "https://jobs.ashbyhq.com/example/rag",
                            "applyUrl": "https://jobs.ashbyhq.com/example/rag/apply",
                            "isListed": True,
                        }
                    ],
                }
            ).encode()

    core = JobFindsMeCore(tmp_path / "ashby.db")
    core.discovery = JobDiscoveryService(
        core.job_imports,
        transport=AshbyTransport(),
    )
    configured = core.configure_search(
        target_roles=["RAG 工程师"],
        locations=["上海"],
        sources=(
            DiscoverySource(
                kind="ashby",
                source_name="示例公司",
                board_name="example",
            ),
        ),
    )

    matches = core.search_jobs()

    assert [item.job.external_id for item in matches] == ["rag"]
    assert configured.sources[0].source.board_name == "example"


def test_local_source_is_read_by_core_not_host_model(tmp_path) -> None:
    source = tmp_path / "jobs.json"
    source.write_text(
        '[{"id":"1","title":"RAG工程师","company":"示例",'
        '"url":"https://example.com/jobs/1"}]',
        encoding="utf-8",
    )
    core = JobFindsMeCore(tmp_path / "discover.db")
    workspace = core.create_workspace("discover")

    summaries = core.discovery.discover(
        workspace_id=workspace.workspace_id,
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="用户导出",
                path=str(source),
            ),
        ),
    )

    assert summaries[0].unique == 1
    assert core.jobs.list(workspace.workspace_id)[0].source.source_url.startswith(
        "file:"
    )


def test_successful_subscription_refresh_closes_missing_source_jobs(tmp_path) -> None:
    class ChangingTransport:
        def __init__(self) -> None:
            self.jobs = [
                {
                    "id": 1,
                    "title": "AI应用工程师",
                    "content": "Python RAG",
                    "absolute_url": "https://example.com/jobs/1",
                }
            ]

        def get(self, _url: str) -> bytes:
            return json.dumps({"jobs": self.jobs}).encode()

    transport = ChangingTransport()
    core = JobFindsMeCore(tmp_path / "discover.db")
    core.discovery = JobDiscoveryService(core.job_imports, transport=transport)
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="greenhouse",
                source_name="企业招聘官网",
                board_token="example",
            ),
        ),
    )

    assert len(core.search_jobs()) == 1
    transport.jobs = []
    assert core.search_jobs() == []

    stored = core.jobs.list(configured.workspace.workspace_id)
    subscriptions = core.source_subscriptions.list(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
    )
    assert stored[0].source.liveness == "closed"
    assert subscriptions[0].health_status == "healthy"


def test_spa_failure_returns_cached_jobs_and_marks_source_degraded(
    tmp_path, monkeypatch
) -> None:
    core = JobFindsMeCore(tmp_path / "spa-cache.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海"],
        sources=(
            DiscoverySource(
                kind="spa_playwright",
                source_name="字节跳动",
                site_key="bytedance",
                query="AI应用工程师",
            ),
        ),
    )
    core.job_imports.import_records(
        configured.workspace.workspace_id,
        [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name="字节跳动",
                source_url="https://jobs.bytedance.com/experienced/position",
                external_id="cached-byte-1",
                payload={
                    "title": "AI应用工程师",
                    "company": "字节跳动",
                    "description": "Python Agent RAG",
                    "location": "上海",
                    "apply_url": "https://jobs.bytedance.com/job/cached-byte-1",
                },
            )
        ],
    )

    def fail_fetch(_self):
        raise TimeoutError("browser timeout")

    monkeypatch.setattr(
        "jobfindsme.connectors.playwright.PlaywrightSpaConnector.fetch",
        fail_fetch,
    )

    matches = core.search_jobs(allow_browser_sources=True)
    subscriptions = core.source_subscriptions.list(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
    )

    assert [item.job.external_id for item in matches] == ["cached-byte-1"]
    assert subscriptions[0].health_status == "degraded"
    assert "browser timeout" in (subscriptions[0].last_error or "")


def test_boss_failure_returns_cached_jobs_and_marks_source_degraded(
    tmp_path, monkeypatch
) -> None:
    core = JobFindsMeCore(tmp_path / "boss-cache.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海"],
        sources=(
            DiscoverySource(
                kind="boss_cdp",
                source_name="BOSS直聘",
                query="AI应用工程师",
            ),
        ),
    )
    core.job_imports.import_records(
        configured.workspace.workspace_id,
        [
            RawJobRecord(
                source_kind=SourceKind.CAREER_SITE,
                source_name="BOSS直聘",
                source_url="https://www.zhipin.com/web/geek/job",
                external_id="cached-boss-1",
                payload={
                    "title": "AI应用工程师",
                    "company": "示例科技",
                    "description": "Python Agent RAG",
                    "location": "上海",
                    "apply_url": (
                        "https://www.zhipin.com/job_detail/cached-boss-1.html"
                    ),
                },
            )
        ],
    )

    def fail_fetch(_self):
        raise RuntimeError("BOSS login required")

    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin.BossZhipinConnector.fetch",
        fail_fetch,
    )

    matches = core.search_jobs(allow_browser_sources=True)
    subscriptions = core.source_subscriptions.list(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
    )

    assert [item.job.external_id for item in matches] == ["cached-boss-1"]
    assert subscriptions[0].health_status == "degraded"
    assert "login required" in (subscriptions[0].last_error or "")


def test_persisted_browser_source_is_not_launched_without_runtime_opt_in(
    tmp_path, monkeypatch
) -> None:
    core = JobFindsMeCore(tmp_path / "browser-safe.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="spa_playwright",
                source_name="字节跳动",
                site_key="bytedance",
                query="AI应用工程师",
            ),
        ),
    )

    def unexpected_fetch(_self):
        raise AssertionError("browser connector must not launch")

    monkeypatch.setattr(
        "jobfindsme.connectors.playwright.PlaywrightSpaConnector.fetch",
        unexpected_fetch,
    )

    assert core.search_jobs() == []
    subscription = core.source_subscriptions.list(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
    )[0]
    assert subscription.health_status == "never_checked"
