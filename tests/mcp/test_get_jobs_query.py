"""get_jobs is the query surface over the local store.

search_jobs refreshes from platforms and applies the opinionated SearchPlan
filter. get_jobs answers questions about what is already collected, with
plain, composable predicates and no plan required.
"""

from __future__ import annotations

from jobfindsme.app import jobfindsmecore
from jobfindsme.importing.parsers import parse_json
from jobfindsme.mcp import ToolRegistry

LIEPIN_JOBS = (
    '[{"id":"a","title":"AI应用工程师","company":"示例科技",'
    '"location":"上海","description":"Python RAG Agent 25-40K",'
    '"url":"https://example.com/jobs/a"},'
    '{"id":"b","title":"AI应用工程师（Agent开发）","company":"第二科技",'
    '"location":"北京","description":"MCP LangChain 30-50K",'
    '"url":"https://example.com/jobs/b"}]'
)

BOSS_JOBS = (
    '[{"id":"c","title":"大模型应用工程师","company":"示例科技",'
    '"location":"上海","description":"Java Spring 10-15K",'
    '"url":"https://example.com/jobs/c"},'
    '{"id":"d","title":"大模型平台工程师","company":"第四科技",'
    '"location":"上海","description":"Go Kubernetes 面议",'
    '"url":"https://example.com/jobs/d"}]'
)


def _registry(tmp_path):
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    workspace_id = core.context.resolve_workspace().workspace_id
    core.job_imports.import_records(
        workspace_id, parse_json(LIEPIN_JOBS, source_name="猎聘")
    )
    core.job_imports.import_records(
        workspace_id, parse_json(BOSS_JOBS, source_name="BOSS直聘")
    )
    return registry


def _query(registry, **arguments):
    result = registry.call("get_jobs", arguments)
    assert result["isError"] is False
    return {job["title"] for job in result["structuredContent"]["jobs"]}


SHANGHAI_TITLES = {
    "AI应用工程师",  # 上海 · 猎聘 · 25-40K
    "大模型应用工程师",  # 上海 · BOSS直聘 · 10-15K
    "大模型平台工程师",  # 上海 · BOSS直聘 · 面议
}


def test_get_jobs_without_filters_returns_everything(tmp_path) -> None:
    registry = _registry(tmp_path)

    result = registry.call("get_jobs", {})

    assert result["structuredContent"]["count"] == 4
    # An unsupplied filter never excludes a job.
    assert _query(registry) == SHANGHAI_TITLES | {"AI应用工程师（Agent开发）"}


def test_keyword_matches_title_company_and_description(tmp_path) -> None:
    registry = _registry(tmp_path)

    assert _query(registry, keyword="LangChain") == {"AI应用工程师（Agent开发）"}
    assert _query(registry, keyword="示例科技") == {"AI应用工程师", "大模型应用工程师"}
    # Lower-case query against mixed-case source text.
    assert _query(registry, keyword="kubernetes") == {"大模型平台工程师"}


def test_location_filter_is_alias_expanded(tmp_path) -> None:
    registry = _registry(tmp_path)

    assert _query(registry, location="上海") == SHANGHAI_TITLES
    assert _query(registry, location="北京") == {"AI应用工程师（Agent开发）"}


def test_salary_bounds_exclude_unverifiable_salary(tmp_path) -> None:
    registry = _registry(tmp_path)

    # 25-40K and 30-50K clear 20K; 10-15K does not; 面议 is not verifiable.
    assert _query(registry, salary_min_k=20) == {
        "AI应用工程师",
        "AI应用工程师（Agent开发）",
    }
    assert _query(registry, salary_max_k=15) == {"大模型应用工程师"}


def test_source_filter(tmp_path) -> None:
    registry = _registry(tmp_path)

    assert _query(registry, source="猎聘") == {
        "AI应用工程师",
        "AI应用工程师（Agent开发）",
    }
    assert _query(registry, source="BOSS直聘") == {
        "大模型应用工程师",
        "大模型平台工程师",
    }


def test_filters_compose(tmp_path) -> None:
    registry = _registry(tmp_path)

    assert _query(registry, location="上海", salary_min_k=20) == {"AI应用工程师"}
    assert _query(registry, keyword="示例科技", location="上海") == {
        "AI应用工程师",
        "大模型应用工程师",
    }
    assert _query(registry, location="北京", source="猎聘") == {
        "AI应用工程师（Agent开发）"
    }


def test_query_filters_apply_before_pagination(tmp_path) -> None:
    registry = _registry(tmp_path)

    page_one = registry.call("get_jobs", {"location": "上海", "limit": 2})
    page_two = registry.call("get_jobs", {"location": "上海", "limit": 2, "offset": 2})

    assert page_one["structuredContent"]["count"] == 2
    assert page_one["structuredContent"]["next_offset"] == 2
    assert page_two["structuredContent"]["count"] == 1
    assert page_two["structuredContent"]["next_offset"] is None


def test_job_id_still_returns_full_details(tmp_path) -> None:
    registry = _registry(tmp_path)
    job_id = registry.call("get_jobs", {"keyword": "LangChain"})["structuredContent"][
        "jobs"
    ][0]["job_id"]

    details = registry.call("get_jobs", {"job_id": job_id})["structuredContent"]

    assert details["job"]["title"] == "AI应用工程师（Agent开发）"
    assert "LangChain" in details["job"]["description"]
