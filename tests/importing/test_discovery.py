from __future__ import annotations

import json

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
