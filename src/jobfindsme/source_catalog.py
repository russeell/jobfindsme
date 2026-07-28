from __future__ import annotations

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> tuple[DiscoverySource, ...]:
    """Return auto-connectors ordered by coverage priority.

    Priority: 四大招聘平台（覆盖全行业）> 国内大厂官网（直达）> SSR 官网（免浏览器）

    CDP / Playwright sources require Chrome; they are skipped gracefully
    when no browser is available. Set allow_browser_sources=True when
    Chrome is running (via ``jobfindsme setup``).
    """

    if not _targets_china(locations):
        return ()
    query = " ".join(roles[:3]) if roles else "AI 大模型 Agent"

    # Tier 1: 四大招聘平台 — 覆盖阿里/华为/京东/网易/拼多多/小红书/快手/小米等全部大厂
    platforms = (
        DiscoverySource(
            kind="boss_cdp",
            source_name="BOSS直聘",
            query=query,
        ),
        DiscoverySource(
            kind="liepin_cdp",
            source_name="猎聘",
            query=query,
        ),
        DiscoverySource(
            kind="zhilian_cdp",
            source_name="智联招聘",
            query=query,
        ),
        DiscoverySource(
            kind="lagou_cdp",
            source_name="拉勾",
            query=query,
        ),
    )
    # Tier 2: 国内互联网大厂官网直达
    companies = (
        DiscoverySource(
            kind="spa_playwright",
            source_name="字节跳动",
            site_key="bytedance",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="美团",
            site_key="meituan",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="滴滴",
            site_key="didi",
            query=query,
        ),
        DiscoverySource(
            kind="spa_playwright",
            source_name="哔哩哔哩",
            site_key="bilibili",
            query=query,
        ),
        DiscoverySource(
            kind="baidu_career",
            source_name="百度招聘",
            query=query,
        ),
    )
    return platforms + companies


def source_links(
    roles: tuple[str, ...],
    locations: tuple[str, ...],
) -> tuple[SourceLink, ...]:
    """Stub — auto-connectors cover all major Chinese sources via BOSS/Liepin/Zhaopin/Lagou CDP."""
    return ()


def _targets_china(locations: tuple[str, ...]) -> bool:
    if not locations:
        return True
    china_markers = (
        "中国", "北京", "上海", "深圳", "杭州",
        "广州", "成都", "武汉", "南京", "苏州", "西安", "重庆",
    )
    return any(
        marker in location for location in locations for marker in china_markers
    )
