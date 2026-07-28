from __future__ import annotations

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> tuple[DiscoverySource, ...]:
    """Return only sources with a maintained public connector contract."""

    if not _targets_china(locations):
        return ()
    query = " ".join(roles[:3]) if roles else "AI 大模型 Agent"
    return (
        DiscoverySource(
            kind="baidu_career",
            source_name="百度招聘",
            query=query,
        ),
        DiscoverySource(
            kind="greenhouse",
            source_name="Airbnb 中国",
            board_token="airbnb",
        ),
        DiscoverySource(
            kind="ashby",
            source_name="Airwallex",
            board_name="airwallex",
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
