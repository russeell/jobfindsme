from jobfindsme.source_catalog import recommended_connectors, source_links


def test_china_search_gets_default_connectors() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    names = {source.source_name for source in sources}
    assert names == {"BOSS直聘", "猎聘", "智联招聘", "拉勾", "前程无忧"}
    assert len(sources) == 5
    assert all(source.kind.uses_browser for source in sources)


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


def test_source_links_returns_empty() -> None:
    links = source_links(("AI应用工程师",), ("上海",))
    assert links == ()
