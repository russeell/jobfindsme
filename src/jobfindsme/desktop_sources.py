from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from jobfindsme.storage import Database

CAPABILITY_STATUSES = {"unverified", "verified", "partial", "blocked", "unavailable"}
SESSION_STATUSES = {"unverified", "anonymous", "verified", "expired", "blocked"}

PLATFORM_SOURCES = (
    (
        "boss",
        "BOSS直聘",
        True,
        "unverified",
        "unverified",
        "unverified",
        "unverified",
        "unverified",
        False,
        None,
        "需要用户在独立桌面会话中完成登录与验证",
    ),
    (
        "liepin",
        "猎聘",
        False,
        "anonymous",
        "verified",
        "unverified",
        "partial",
        "unverified",
        True,
        "2026-09-19T00:00:00+00:00",
        "匿名 HTTP 列表：2026-09-19 生产 .app 快照 92 条，"
        "桌面结果 5 页且第二页稳定；官方原页完整 JD 已可视核验。"
        "列表 description 仍为摘要，未声明结构化完整 JD；"
        "桌面快照页数不代表来源全量分页。",
    ),
    (
        "zhilian",
        "智联招聘",
        True,
        "unverified",
        "unverified",
        "unverified",
        "unverified",
        "unverified",
        False,
        None,
        "需要用户在独立桌面会话中完成登录与验证",
    ),
    (
        "wuyou",
        "前程无忧",
        True,
        "unverified",
        "unverified",
        "unverified",
        "unverified",
        "unverified",
        False,
        None,
        "需要用户在独立桌面会话中完成登录与验证",
    ),
)

COMPANY_NAMES = (
    "腾讯",
    "字节跳动",
    "阿里巴巴",
    "美团",
    "百度",
    "京东",
    "网易",
    "快手",
    "小米",
    "滴滴",
    "拼多多",
    "DeepSeek",
    "MiniMax",
    "智谱",
    "月之暗面",
    "阶跃星辰",
)


class SourceGateError(PermissionError):
    pass


@dataclass(frozen=True)
class SourceCapabilityRecord:
    source_id: str
    source_type: str
    name: str
    login_required: bool
    session_status: str
    list_status: str
    detail_status: str
    fields_status: str
    pagination_status: str
    enabled: bool
    last_verified_at: str | None
    notes: str

    @property
    def live_search_enabled(self) -> bool:
        if not self.enabled or self.list_status != "verified":
            return False
        if self.login_required:
            return self.session_status == "verified"
        return self.session_status in {"anonymous", "verified"}


class DesktopSourceService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.database.migrate()
        self._seed_catalog()

    def _seed_catalog(self) -> None:
        with self.database.connect() as connection:
            connection.executemany(
                """INSERT INTO desktop_source_capabilities (
                    source_id, source_type, name, login_required, session_status,
                    list_status, detail_status, fields_status, pagination_status,
                    enabled, last_verified_at, notes
                ) VALUES (?, 'platform', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO NOTHING""",
                PLATFORM_SOURCES,
            )
            connection.executemany(
                """INSERT INTO desktop_source_capabilities (
                    source_id, source_type, name, login_required, session_status,
                    list_status, detail_status, fields_status, pagination_status,
                    enabled, last_verified_at, notes
                ) VALUES (?, 'company', ?, 0, 'anonymous', 'unverified',
                    'unverified', 'unverified', 'unverified', 0, NULL, ?)
                ON CONFLICT(source_id) DO NOTHING""",
                [
                    (
                        f"company_{index:02d}",
                        name,
                        "校招/社招入口、列表、详情、字段和分页均待逐项验证",
                    )
                    for index, name in enumerate(COMPANY_NAMES, start=1)
                ],
            )
            connection.execute(
                """UPDATE desktop_source_capabilities SET
                    session_status = 'anonymous', list_status = 'verified',
                    detail_status = 'verified', fields_status = 'partial',
                    pagination_status = 'verified', enabled = 1,
                    last_verified_at = '2026-09-18T00:00:00+00:00',
                    notes = '腾讯官网 JSON 已实测列表、JD 与分页；无薪资字段。'
                WHERE source_id = 'company_01' AND list_status = 'unverified'"""
            )
            connection.execute(
                """UPDATE desktop_source_capabilities SET
                    list_status='verified', detail_status='verified',
                    fields_status='partial', pagination_status='unverified', enabled=1,
                    last_verified_at='2026-09-19T00:00:00+00:00',
                    notes='官网岗位快照：2026-09-19 实读34条，Agent匹配15条。'
                    || '含完整JD；快照日期2026-09-17，不代表ATS实时全量。'
                    || '城市本地筛选，薪资未提供。'
                WHERE source_id='company_12' AND list_status='unverified'"""
            )
            # Enable only sources with a real list and a full-JD sample in D37.
            for source_id, note in (
                ("company_02", "字节跳动实读2条及完整JD520字；覆盖及分页待验证。"),
                ("company_04", "美团实读10条及完整JD915字；点击式列表，分页待验证。"),
                ("company_05", "百度实读5条及完整JD350字；点击式列表，分页待验证。"),
                ("company_06", "京东2026-09-20实读两页，北京本地筛选17条，完整JD457字；有界覆盖。"),
                ("company_09", "小米实读9条及官方详情接口完整JD315字；分页待验证。"),
                ("company_10", "滴滴实读6条及完整JD557字；分页待验证。"),
                ("company_07", "网易实读1条及完整JD918字；点击式列表，分页尚待验证。"),
                ("company_08", "快手校招实读1条及完整JD987字；分页尚待验证。"),
                ("company_11", "拼多多实读18条及完整JD400字；分页尚待验证。"),
                (
                    "company_13",
                    "MiniMax实读10条及官方详情接口完整JD598字；分页待验证。",
                ),
                ("company_14", "智谱Moka实读两页42条及完整JD678字。"),
                ("company_15", "月之暗面Moka实读两页39条及完整JD824字。"),
                ("company_16", "阶跃星辰Moka实读两页60条及完整JD688字。"),
            ):
                connection.execute(
                    """UPDATE desktop_source_capabilities SET
                        list_status='verified', detail_status='verified',
                        fields_status='partial', pagination_status='partial',
                        enabled=1, last_verified_at='2026-09-19T12:40:00+00:00',
                        notes=? WHERE source_id=? AND list_status='unverified'""",
                    (note + "关键词/城市在有界候选中筛选，未知字段保留。", source_id),
                )

    def list(self, *, source_type: str | None = None) -> list[SourceCapabilityRecord]:
        with self.database.connect() as connection:
            if source_type is None:
                rows = connection.execute(
                    """SELECT * FROM desktop_source_capabilities
                    ORDER BY source_type DESC, rowid"""
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM desktop_source_capabilities
                    WHERE source_type = ? ORDER BY rowid""",
                    (source_type,),
                ).fetchall()
        return [_record(row) for row in rows]

    def get(self, source_id: str) -> SourceCapabilityRecord:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM desktop_source_capabilities WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        if row is None:
            raise LookupError(source_id)
        return _record(row)

    def require_live_search(self, source_id: str) -> SourceCapabilityRecord:
        source = self.get(source_id)
        if not source.live_search_enabled:
            if source.login_required and source.session_status != "verified":
                raise SourceGateError(
                    f"{source.name} requires a verified login session"
                )
            raise SourceGateError(
                f"{source.name} list search capability is not verified"
            )
        if source.source_type not in {"platform", "company"}:
            raise SourceGateError(f"{source.name} has no verified search adapter")
        return source

    def record_verification(
        self,
        *,
        source_id: str,
        session_status: str,
        list_status: str,
        detail_status: str,
        fields_status: str,
        pagination_status: str,
        enabled: bool,
        notes: str,
    ) -> SourceCapabilityRecord:
        if session_status not in SESSION_STATUSES:
            raise ValueError("invalid source session status")
        statuses = {list_status, detail_status, fields_status, pagination_status}
        if not statuses <= CAPABILITY_STATUSES:
            raise ValueError("invalid source capability status")
        existing = self.get(source_id)
        if (
            existing.login_required
            and enabled
            and (session_status != "verified" or list_status != "verified")
        ):
            raise SourceGateError(
                "login-gated sources require verified session and list capability"
            )
        if not existing.login_required and enabled and list_status != "verified":
            raise SourceGateError("anonymous source requires verified list capability")
        with self.database.connect() as connection:
            connection.execute(
                """UPDATE desktop_source_capabilities SET
                    session_status = ?, list_status = ?, detail_status = ?,
                    fields_status = ?, pagination_status = ?, enabled = ?,
                    last_verified_at = ?, notes = ? WHERE source_id = ?""",
                (
                    session_status,
                    list_status,
                    detail_status,
                    fields_status,
                    pagination_status,
                    int(enabled),
                    datetime.now(UTC).isoformat(),
                    notes,
                    source_id,
                ),
            )
        return self.get(source_id)

    def record_runtime_failure(
        self, *, source_id: str, failure: str, notes: str
    ) -> SourceCapabilityRecord:
        existing = self.get(source_id)
        if existing.source_type != "platform":
            raise ValueError("runtime source failure is only valid for platforms")
        session_status = "expired" if failure == "login_required" else "blocked"
        with self.database.connect() as connection:
            connection.execute(
                """UPDATE desktop_source_capabilities SET
                    session_status = ?, list_status = 'blocked', enabled = 0,
                    last_verified_at = ?, notes = ? WHERE source_id = ?""",
                (
                    session_status,
                    datetime.now(UTC).isoformat(),
                    notes[:1000],
                    source_id,
                ),
            )
        return self.get(source_id)


def _record(row) -> SourceCapabilityRecord:
    return SourceCapabilityRecord(
        source_id=row["source_id"],
        source_type=row["source_type"],
        name=row["name"],
        login_required=bool(row["login_required"]),
        session_status=row["session_status"],
        list_status=row["list_status"],
        detail_status=row["detail_status"],
        fields_status=row["fields_status"],
        pagination_status=row["pagination_status"],
        enabled=bool(row["enabled"]),
        last_verified_at=row["last_verified_at"],
        notes=row["notes"],
    )
