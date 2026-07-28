from __future__ import annotations

from urllib.parse import quote_plus

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
) -> tuple[DiscoverySource, ...]:
    """Return only sources with a maintained public connector contract."""

    if not _targets_china(locations):
        return ()
    return (
        DiscoverySource(
            kind="baidu_career",
            source_name="百度招聘",
            query="AI Agent RAG 大模型",
        ),
        DiscoverySource(
            kind="ashby",
            source_name="Airwallex 官方招聘",
            board_name="airwallex",
        ),
    )


def source_links(
    roles: tuple[str, ...],
    locations: tuple[str, ...],
) -> tuple[SourceLink, ...]:
    """Official live-search links; link-only entries are never scraped."""

    query = " ".join((*roles, *locations)).strip() or "AI 工程师"
    encoded = quote_plus(query)
    return (
        SourceLink(
            name="华为招聘",
            category="企业官网",
            url="https://career.huawei.com/reccampportal/portal5/"
            "social-recruitment-ai.html",
            access_mode="official_link",
            note="AI 社会招聘专区",
        ),
        SourceLink(
            name="百度招聘",
            category="企业官网",
            url=f"https://talent.baidu.com/jobs/list?search={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="腾讯招聘",
            category="企业官网",
            url="https://careers.tencent.com/zh-cn/search.html",
            access_mode="official_link",
        ),
        SourceLink(
            name="字节跳动招聘",
            category="企业官网",
            url=f"https://jobs.bytedance.com/experienced/position?keywords={encoded}",
            access_mode="official_link",
        ),
        SourceLink(
            name="BOSS直聘",
            category="招聘平台",
            url=f"https://www.zhipin.com/web/geek/job?query={encoded}",
            access_mode="user_browser",
            note="需要用户在官方平台完成登录与查看",
        ),
        SourceLink(
            name="猎聘",
            category="招聘平台",
            url=f"https://www.liepin.com/zhaopin/?key={encoded}",
            access_mode="user_browser",
            note="不通过未授权接口抓取",
        ),
        SourceLink(
            name="智联招聘",
            category="招聘平台",
            url=f"https://sou.zhaopin.com/?kw={encoded}",
            access_mode="user_browser",
            note="不通过未授权接口抓取",
        ),
        SourceLink(
            name="前程无忧",
            category="招聘平台",
            url=f"https://we.51job.com/pc/search?keyword={encoded}",
            access_mode="user_browser",
            note="不通过未授权接口抓取",
        ),
    )


def _targets_china(locations: tuple[str, ...]) -> bool:
    if not locations:
        return True
    china_markers = (
        "中国",
        "北京",
        "上海",
        "深圳",
        "杭州",
        "广州",
        "成都",
        "武汉",
        "南京",
        "苏州",
        "西安",
        "重庆",
    )
    return any(marker in location for location in locations for marker in china_markers)
