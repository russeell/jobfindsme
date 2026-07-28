from jobfindsme.source_catalog import recommended_connectors, source_links


def test_china_search_gets_default_connectors() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    names = {source.source_name for source in sources}
    # Four platforms cover all Chinese companies
    assert names == {"BOSS直聘", "猎聘", "智联招聘", "拉勾"}
    assert len(sources) == 4
    # All are CDP (browser-backed)
    assert all(source.kind.uses_browser for source in sources)


def test_source_links_returns_empty() -> None:
    """Manual links have been removed — all companies covered by auto-connectors."""
    links = source_links(("AI应用工程师",), ("上海",))
    assert links == ()
