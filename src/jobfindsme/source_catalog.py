from __future__ import annotations

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> tuple[DiscoverySource, ...]:
    """Return the five recruitment platforms for broadest reach.

    No single source covers every position — some roles may appear only on
    company career sites or internal referral channels. These five platforms
    together provide the widest coverage with minimal maintenance.
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
    """Stub — auto-connectors now cover the major Chinese platforms via CDP."""
    return ()


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
