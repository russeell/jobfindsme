from __future__ import annotations

from collections.abc import Sequence

from jobfindsme.contracts import DiscoverySource, SourceLink


def recommended_connectors(
    locations: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> tuple[DiscoverySource, ...]:
    """Return the maintained recruitment platforms for broad China coverage.

    No single source covers every position — some roles may appear only on
    company career sites or internal referral channels. The catalog includes
    only sources that currently pass the project's live-source quality bar.
    """

    if not _targets_china(locations):
        return ()
    query = roles[0] if roles else "AI"
    requested_locations = tuple(dict.fromkeys(locations)) or (None,)
    platforms = (
        ("boss_cdp", "BOSS直聘"),
        ("liepin_http", "猎聘"),
    )
    # Old source kinds remain readable for database compatibility, but only
    # these two evidence-backed connectors are executable in production.
    multiple_locations = len(requested_locations) > 1
    return tuple(
        DiscoverySource(
            kind=kind,
            source_name=(
                f"{name}·{location}" if multiple_locations and location else name
            ),
            catalog_managed=True,
            location=location,
            query=query,
        )
        for kind, name in platforms
        for location in requested_locations
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
        if not source.kind.retired
        and not source.catalog_managed
        and (
            not legacy_managed or (source.kind, source.source_name) not in current_keys
        )
    )
    return custom + current


def source_links(
    roles: tuple[str, ...],
    locations: tuple[str, ...],
) -> tuple[SourceLink, ...]:
    """Stub for future official career-site links."""
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
