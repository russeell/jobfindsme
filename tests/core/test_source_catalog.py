from jobfindsme.contracts import DiscoverySource
from jobfindsme.source_catalog import (
    recommended_connectors,
    reconcile_catalog_sources,
    source_links,
)


def test_china_search_gets_default_connectors() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    names = {source.source_name for source in sources}
    assert names == {
        "BOSS直聘·上海",
        "BOSS直聘·杭州",
        "猎聘·上海",
        "猎聘·杭州",
        "智联招聘·上海",
        "智联招聘·杭州",
        "拉勾·上海",
        "拉勾·杭州",
        "前程无忧·上海",
        "前程无忧·杭州",
    }
    assert len(sources) == 10
    assert all(source.kind.uses_browser for source in sources)
    assert all(source.catalog_managed for source in sources)
    assert {source.location for source in sources} == {"上海", "杭州"}


def test_query_uses_only_first_role() -> None:
    """M24-001: queries use primary role, not concatenation of all roles."""
    sources = recommended_connectors(
        ("上海",), ("AI Agent工程师", "大模型应用", "智能体")
    )
    for source in sources:
        # Query should be the first role, not a concatenation
        assert source.query == "AI Agent工程师"


def test_partial_snapshot_sources_flag_browser_access() -> None:
    """M24-001: browser-backed sources are identifiable as partial snapshots."""
    sources = recommended_connectors(("上海", "杭州"))
    for source in sources:
        assert source.kind.uses_browser


def test_catalog_reconciliation_updates_queries_and_preserves_custom_source() -> None:
    existing = recommended_connectors(("上海",), ("AI应用工程师",))
    custom = DiscoverySource(
        kind="json_file",
        source_name="我的岗位",
        path="/tmp/jobs.json",
    )

    reconciled = reconcile_catalog_sources(
        existing + (custom,),
        locations=("杭州",),
        roles=("RAG工程师",),
    )

    managed = [source for source in reconciled if source.catalog_managed]
    assert len(managed) == 5
    assert {source.query for source in managed} == {"RAG工程师"}
    assert {source.location for source in managed} == {"杭州"}
    assert custom in reconciled


def test_custom_browser_source_is_not_treated_as_catalog_plan() -> None:
    custom = DiscoverySource(
        kind="boss_cdp",
        source_name="我的BOSS搜索",
        query="只找远程岗位",
    )

    reconciled = reconcile_catalog_sources(
        (custom,),
        locations=("上海",),
        roles=("RAG工程师",),
    )

    assert reconciled == (custom,)


def test_source_links_returns_empty() -> None:
    links = source_links(("AI应用工程师",), ("上海",))
    assert links == ()
