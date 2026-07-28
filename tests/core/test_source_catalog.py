from jobfindsme.source_catalog import recommended_connectors, source_links


def test_china_search_gets_default_connectors() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    names = {source.source_name for source in sources}
    # Tier 1: 四大招聘平台
    assert "BOSS直聘" in names
    assert "猎聘" in names
    assert "智联招聘" in names
    assert "拉勾" in names
    # Tier 2: 国内大厂官网
    assert "字节跳动" in names
    assert "美团" in names
    assert "滴滴" in names
    assert "哔哩哔哩" in names
    assert "百度招聘" in names
    # Total 9 sources
    assert len(sources) == 9
    # Browser sources are present (CDP + Playwright)
    assert any(source.kind.uses_browser for source in sources)
    # Non-browser sources also present
    assert any(not source.kind.uses_browser for source in sources)


def test_source_links_returns_empty() -> None:
    """Manual links have been removed — all companies covered by auto-connectors."""
    links = source_links(("AI应用工程师",), ("上海",))
    assert links == ()
