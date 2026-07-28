from jobfindsme.source_catalog import recommended_connectors, source_links


def test_china_search_gets_default_connectors() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    assert {source.source_name for source in sources} == {
        "百度招聘",
        "Airbnb 中国",
        "Airwallex",
    }
    assert all(not source.kind.uses_browser for source in sources)
    assert next(source for source in sources if source.kind == "baidu_career").query


def test_source_links_returns_empty() -> None:
    """Manual links have been removed — all companies covered by auto-connectors."""
    links = source_links(("AI应用工程师",), ("上海",))
    assert links == ()
