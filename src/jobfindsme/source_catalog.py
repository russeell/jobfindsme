from __future__ import annotations

from collections.abc import Sequence

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
    query = roles[0] if roles else "AI"
    location = locations[0] if locations else None

    return (
        DiscoverySource(
            kind="boss_cdp",
            source_name="BOSS直聘",
            catalog_managed=True,
            location=location,
            query=query,
        ),
        DiscoverySource(
            kind="liepin_cdp",
            source_name="猎聘",
            catalog_managed=True,
            location=location,
            query=query,
        ),
        DiscoverySource(
            kind="zhilian_cdp",
            source_name="智联招聘",
            catalog_managed=True,
            location=location,
            query=query,
        ),
        DiscoverySource(
            kind="lagou_cdp",
            source_name="拉勾",
            catalog_managed=True,
            location=location,
            query=query,
        ),
        DiscoverySource(
            kind="wuyou_cdp",
            source_name="前程无忧",
            catalog_managed=True,
            location=location,
            query=query,
        ),
    )


def reconcile_catalog_sources(
    existing: Sequence[DiscoverySource],
    *,
    locations: tuple[str, ...],
    roles: tuple[str, ...],
) -> tuple[DiscoverySource, ...]:
    """Upgrade catalog sources while preserving explicitly custom sources."""

    current = recommended_connectors(locations, roles)
    current_keys = {(source.kind, source.source_name) for source in current}
    existing_keys = {(source.kind, source.source_name) for source in existing}
    managed = any(source.catalog_managed for source in existing)
    # Before catalog_managed existed, a default plan contained the full catalog.
    legacy_managed = bool(current_keys) and current_keys <= existing_keys
    if not managed and not legacy_managed:
        return tuple(existing)

    custom = tuple(
        source
        for source in existing
        if not source.catalog_managed
        and (
            not legacy_managed or (source.kind, source.source_name) not in current_keys
        )
    )
    return custom + current


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
