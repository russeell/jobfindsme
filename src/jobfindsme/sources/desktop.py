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
            # Keep historical company rows and their linked job evidence readable,
            # but never offer them as current search capabilities again.
            connection.execute(
                """UPDATE desktop_source_capabilities SET enabled = 0
                WHERE source_type = 'company'"""
            )

    def list(self, *, source_type: str | None = None) -> list[SourceCapabilityRecord]:
        with self.database.connect() as connection:
            if source_type is None:
                rows = connection.execute(
                    """SELECT * FROM desktop_source_capabilities
                    WHERE source_type = 'platform' ORDER BY rowid"""
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
        if source.source_type != "platform":
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
        if existing.source_type != "platform":
            raise SourceGateError("retired source cannot be verified")
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
