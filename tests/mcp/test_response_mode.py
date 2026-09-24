"""response_mode: bounded facts with or without Server-rendered prose.

`summary` is the conversational default and what the canonical Skill is
validated against. `facts` exists so a programmatic caller can render its
own output instead of relaying Server-authored recommendations and
next-step advice, while receiving byte-identical structured facts.
"""

from __future__ import annotations

from jobfindsme.app import jobfindsmecore
from jobfindsme.contracts import ResponseMode
from jobfindsme.importing.parsers import parse_json
from jobfindsme.mcp import ToolRegistry
from jobfindsme.mcp.schemas import SearchJobsInput

_JOBS_JSON = (
    '[{"id":"a","title":"AI应用工程师",'
    '"company":"示例科技","location":"上海",'
    '"description":"Python RAG Agent 25-40K",'
    '"url":"https://example.com/jobs/a"},'
    '{"id":"b","title":"AI应用工程师（Agent开发）",'
    '"company":"第二科技","location":"上海",'
    '"description":"MCP LangChain 30-50K",'
    '"url":"https://example.com/jobs/b"}]'
)

# The radar suppresses unchanged seen jobs, so comparing two searches on the
# same plan requires include_seen — otherwise the second call returns nothing.
_CACHE_SEARCH = {"refresh_mode": "cache", "include_seen": True}


def _registry(tmp_path):
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    registry = ToolRegistry(core)
    registry.call(
        "setup",
        {
            "target_role": "AI应用工程师",
            "locations": ["上海"],
            "recruitment_track": "social",
            "employment_type": "full_time",
        },
    )
    workspace_id = core.context.resolve_workspace().workspace_id
    core.job_imports.import_records(
        workspace_id,
        parse_json(_JOBS_JSON, source_name="猎聘"),
    )
    return registry


def test_response_mode_defaults_to_summary() -> None:
    assert SearchJobsInput().response_mode is ResponseMode.SUMMARY


def test_summary_mode_renders_the_three_layer_prose(tmp_path) -> None:
    registry = _registry(tmp_path)

    result = registry.call("search_jobs", dict(_CACHE_SEARCH))

    text = result["content"][0]["text"]
    assert result["structuredContent"]["count"] == 2
    assert "【搜索摘要】" in text
    assert "【推荐岗位】" in text
    assert "【状态与下一步】" in text
    assert "推荐理由：" in text
    assert "投递链接：https://example.com/jobs/a" in text


def test_facts_mode_omits_server_rendered_prose(tmp_path) -> None:
    registry = _registry(tmp_path)

    result = registry.call(
        "search_jobs",
        {**_CACHE_SEARCH, "response_mode": "facts"},
    )

    text = result["content"][0]["text"]
    for fragment in (
        "【搜索摘要】",
        "【推荐岗位】",
        "【状态与下一步】",
        "推荐理由：",
        "投递链接：",
        "建议：优先查看",
        "下一步（直接和 AI 说）",
        "对我说",
    ):
        assert fragment not in text
    # The status line keeps source health and change counts — the only prose
    # a programmatic caller cannot recompute from `jobs`.
    assert "检索：" in text
    assert "新增" in text
    assert "重复抑制" in text
    assert len(text.splitlines()) == 1


def test_facts_mode_keeps_identical_structured_facts(tmp_path) -> None:
    registry = _registry(tmp_path)

    summary = registry.call("search_jobs", dict(_CACHE_SEARCH))
    facts = registry.call(
        "search_jobs",
        {**_CACHE_SEARCH, "response_mode": "facts"},
    )

    def facts_of(result):
        return [item["job"] for item in result["structuredContent"]["jobs"]]

    assert facts_of(facts) == facts_of(summary)
    assert facts["structuredContent"]["count"] == summary["structuredContent"]["count"]
    assert (
        facts["structuredContent"]["diagnostic_summary"]
        == summary["structuredContent"]["diagnostic_summary"]
    )
    # Bare apply URLs stay available to the caller in both modes.
    urls = [item["job"]["apply_url"] for item in facts["structuredContent"]["jobs"]]
    assert "https://example.com/jobs/a" in urls


def test_facts_mode_survives_output_schema_validation(tmp_path) -> None:
    registry = _registry(tmp_path)

    result = registry.call(
        "search_jobs",
        {**_CACHE_SEARCH, "response_mode": "facts"},
    )

    assert result["isError"] is False
    assert result["structuredContent"]["summary"] == result["content"][0]["text"]
