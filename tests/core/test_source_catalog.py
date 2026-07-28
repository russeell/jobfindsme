from urllib.parse import unquote_plus

from jobfindsme.source_catalog import recommended_connectors, source_links


def test_china_search_gets_maintained_connector_without_ats_parameters() -> None:
    sources = recommended_connectors(("上海", "杭州"))

    assert sources
    assert {source.source_name for source in sources} == {
        "百度-AI应用工程师",
        "百度-大模型",
        "Airbnb 中国",
        "Airwallex",
    }
    assert next(source for source in sources if source.kind == "baidu_career").query


def test_catalog_links_official_careers_and_platform_live_search() -> None:
    links = source_links(("AI应用工程师",), ("上海",))
    names = {link.name for link in links}

    assert {"华为招聘", "百度招聘", "腾讯招聘", "字节跳动招聘"} <= names
    assert {"BOSS直聘", "猎聘", "智联招聘", "前程无忧"} <= names
    boss = next(link for link in links if link.name == "BOSS直聘")
    assert "AI应用工程师" in unquote_plus(boss.url)
    assert boss.access_mode == "user_browser"
