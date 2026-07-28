from __future__ import annotations

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> tuple[DiscoverySource, ...]:
    """Return the four recruitment platforms — they cover all Chinese companies.

    Company career sites (Playwright/SSR) and foreign ATS (Greenhouse/Ashby/
    Lever) are available via explicit sources but excluded from defaults:
    BOSS + 猎聘 + 智联 + 拉勾 already list every major company's jobs.
    """

    if not _targets_china(locations):
        return ()
    query = " ".join(roles[:3]) if roles else "AI 大模型 Agent"

    return (
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
        DiscoverySource(
            kind="wuyou_cdp",
            source_name="前程无忧",
            query=query,
        ),
    )


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
