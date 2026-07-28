from urllib.parse import unquote_plus

from jobfindsme.source_catalog import recommended_connectors, source_links


def test_china_search_gets_maintained_connector_without_ats_parameters() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    assert {source.source_name for source in sources} == {
        "百度招聘",
        "字节跳动",
        "美团",
        "Airbnb 中国",
        "Airwallex",
    }
    assert next(source for source in sources if source.kind == "baidu_career").query
    assert all(source.source_name != "BOSS直聘" for source in sources)


def test_catalog_links_official_careers_and_platform_live_search() -> None:
    links = source_links(("AI应用工程师",), ("上海",))
    names = {link.name for link in links}

    # Verified defaults and explicitly classified non-default sources
    assert "腾讯招聘" in names
    assert "字节跳动招聘 (自动)" in names
    assert "美团招聘 (自动)" in names
    assert "滴滴招聘 (Beta)" in names
    assert "哔哩哔哩招聘 (Beta)" in names
    assert "Airbnb 中国 (自动)" in names

    # Big tech career sites (manual)
    assert {"阿里巴巴招聘", "华为招聘"} <= names
    assert {"京东招聘", "网易招聘", "拼多多招聘"} <= names

    # Known tech
    assert {"小红书招聘", "快手招聘", "小米招聘"} <= names
    assert {"蚂蚁集团招聘"} <= names

    # Recruitment platforms
    assert {
        "BOSS直聘 (Experimental)",
        "猎聘",
        "智联招聘",
        "前程无忧",
    } <= names
    boss = next(link for link in links if "BOSS" in link.name)
    assert "AI应用工程师" in unquote_plus(boss.url)
    assert boss.access_mode == "user_browser"
    assert "尚未完成" in boss.note
