from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import Field

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import ExportReceipt, StrictModel
from jobfindsme.storage import Database

Clock = Callable[[], datetime]

PERSONAL_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    "phone": re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9](?:[- ]?\d){9}(?!\d)"),
    "id_number": re.compile(r"(?<!\d)(?:\d{15}|\d{17}[\dXx])(?![\dXx])"),
    "address": re.compile(
        r"(?<![\u4e00-\u9fff])(?:现居地|家庭住址|联系地址|住址|地址)[：:]\s*"
        r"[^\n,;，；\"}]{3,80}",
        re.IGNORECASE,
    ),
    "name": re.compile(
        r"(?<![\u4e00-\u9fff])(?:姓名|名字)[：:]\s*[\u4e00-\u9fff·]{2,20}",
    ),
}


class AnalysisCopy(StrictModel):
    source_version_id: str
    redacted_fields: tuple[str, ...]
    text: str
    limitations: str


def create_analysis_copy(
    *,
    source_version_id: str,
    text: str,
    redacted_fields: set[str] | None = None,
) -> AnalysisCopy:
    """Create a transient model-facing copy without mutating stored content."""

    requested = (
        set(PERSONAL_FIELD_PATTERNS)
        if redacted_fields is None
        else set(redacted_fields)
    )
    unknown = requested - PERSONAL_FIELD_PATTERNS.keys()
    if unknown:
        raise ValueError(f"unknown personal fields: {sorted(unknown)}")
    result = text
    for field in sorted(requested):
        result = PERSONAL_FIELD_PATTERNS[field].sub(f"[已过滤:{field}]", result)
    return AnalysisCopy(
        source_version_id=source_version_id,
        redacted_fields=tuple(sorted(requested)),
        text=result,
        limitations=("脱敏使用结构化字段与常见文本格式规则；发送前仍应检查预览。"),
    )


class DeletionPreview(StrictModel):
    workspace_id: str
    scope: str
    record_counts: dict[str, int]
    confirmation_token: str = Field(min_length=32)
    expires_at: datetime


class DeletionResult(StrictModel):
    workspace_id: str
    scope: str
    deleted: bool
    deleted_at: datetime


class PrivacyService:
    VALID_SCOPES = {"jobs", "profile", "workspace"}

    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self.database = database
        self.clock = clock

    def export_workspace(self, workspace_id: str) -> dict[str, object]:
        with self.database.connect() as connection:
            workspace = connection.execute(
                "SELECT * FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            if workspace is None:
                raise LookupError(workspace_id)
            plans = connection.execute(
                "SELECT * FROM search_plans WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
            jobs = connection.execute(
                "SELECT payload_json FROM jobs WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
            states = connection.execute(
                "SELECT * FROM job_states WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
            state_events = connection.execute(
                """
                SELECT * FROM job_state_events
                WHERE workspace_id = ? ORDER BY created_at, event_id
                """,
                (workspace_id,),
            ).fetchall()
            impressions = connection.execute(
                """
                SELECT * FROM search_job_impressions
                WHERE workspace_id = ? ORDER BY plan_id, first_shown_at, job_id
                """,
                (workspace_id,),
            ).fetchall()
            facts = connection.execute(
                """
                SELECT fact_type, current_value, evidence_snippet, status
                FROM profile_facts WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchall()
        return {
            "schema_version": "1.0",
            "workspace": dict(workspace),
            "search_plans": [dict(row) for row in plans],
            "jobs": [json.loads(row["payload_json"]) for row in jobs],
            "job_states": [dict(row) for row in states],
            "job_state_events": [dict(row) for row in state_events],
            "search_job_impressions": [dict(row) for row in impressions],
            "profile_facts": [dict(row) for row in facts],
        }

    def export_workspace_to_file(self, workspace_id: str) -> ExportReceipt:
        payload = self.export_workspace(workspace_id)
        exported_at = self.clock()
        directory = self.database.path.parent / "exports"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = directory / (
            f"agent-job-search-{workspace_id}-{exported_at:%Y%m%dT%H%M%S%fZ}.json"
        )
        content = (
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
        ).encode()
        destination.write_bytes(content)
        destination.chmod(0o600)
        counts = {
            key: len(value) for key, value in payload.items() if isinstance(value, list)
        }
        return ExportReceipt(
            path=str(destination),
            sha256=hashlib.sha256(content).hexdigest(),
            record_counts=counts,
        )

    def preview_delete(self, *, workspace_id: str, scope: str) -> DeletionPreview:
        self._validate_scope(scope)
        counts = self._scope_counts(workspace_id, scope)
        # Keep the token safe as a CLI value even if token_urlsafe() would
        # otherwise begin with "-" and be parsed as an option.
        token = f"del_{secrets.token_urlsafe(32)}"
        expires_at = self.clock() + timedelta(minutes=10)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO deletion_tokens (
                    token_hash, workspace_id, scope, expires_at, used_at
                ) VALUES (?, ?, ?, ?, NULL)
                """,
                (
                    _token_hash(token),
                    workspace_id,
                    scope,
                    expires_at.isoformat(),
                ),
            )
        return DeletionPreview(
            workspace_id=workspace_id,
            scope=scope,
            record_counts=counts,
            confirmation_token=token,
            expires_at=expires_at,
        )

    def confirm_delete(
        self,
        *,
        workspace_id: str,
        scope: str,
        confirmation_token: str,
    ) -> DeletionResult:
        self._validate_scope(scope)
        now = self.clock()
        token_hash = _token_hash(confirmation_token)
        managed_paths: list[str] = []
        with self.database.connect() as connection:
            token = connection.execute(
                """
                SELECT * FROM deletion_tokens
                WHERE token_hash = ? AND workspace_id = ? AND scope = ?
                """,
                (token_hash, workspace_id, scope),
            ).fetchone()
            if (
                token is None
                or token["used_at"] is not None
                or datetime.fromisoformat(token["expires_at"]) < now
            ):
                raise PermissionError("invalid or expired confirmation token")
            if scope in {"profile", "workspace"}:
                managed_paths = [
                    row["managed_path"]
                    for row in connection.execute(
                        """
                        SELECT managed_path FROM source_documents
                        WHERE workspace_id = ? AND managed_path IS NOT NULL
                        """,
                        (workspace_id,),
                    ).fetchall()
                ]
                for managed_path in managed_paths:
                    Path(managed_path).unlink(missing_ok=True)
            if scope == "jobs":
                connection.execute(
                    "DELETE FROM jobs WHERE workspace_id = ?", (workspace_id,)
                )
            elif scope == "profile":
                connection.execute(
                    "DELETE FROM source_documents WHERE workspace_id = ?",
                    (workspace_id,),
                )
            else:
                connection.execute(
                    "DELETE FROM workspaces WHERE workspace_id = ?",
                    (workspace_id,),
                )
            connection.execute(
                "DELETE FROM deletion_tokens WHERE token_hash = ?",
                (token_hash,),
            )
            connection.execute(
                """
                INSERT INTO deletion_audit (
                    workspace_hash, scope, deleted_at
                ) VALUES (?, ?, ?)
                """,
                (
                    hashlib.sha256(workspace_id.encode()).hexdigest(),
                    scope,
                    now.isoformat(),
                ),
            )
        return DeletionResult(
            workspace_id=workspace_id,
            scope=scope,
            deleted=True,
            deleted_at=now,
        )

    def _counts(self, workspace_id: str) -> dict[str, int]:
        tables = {
            "search_plans": "search_plans",
            "profiles": "candidate_profiles",
            "jobs": "jobs",
            "job_states": "job_states",
        }
        with self.database.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            if exists is None:
                raise LookupError(workspace_id)
            return {
                name: connection.execute(
                    f"SELECT count(*) FROM {table} WHERE workspace_id = ?",
                    (workspace_id,),
                ).fetchone()[0]
                for name, table in tables.items()
            }

    def _scope_counts(self, workspace_id: str, scope: str) -> dict[str, int]:
        """Preview counts must describe what this exact scope will delete."""
        all_counts = self._counts(workspace_id)
        if scope == "jobs":
            return {"jobs": all_counts["jobs"]}
        if scope == "profile":
            return {
                "profiles": all_counts["profiles"],
            }
        return all_counts

    @classmethod
    def _validate_scope(cls, scope: str) -> None:
        if scope not in cls.VALID_SCOPES:
            raise ValueError(f"invalid deletion scope: {scope}")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PrivacyUseCase:
    def __init__(
        self,
        *,
        context: ActiveContextService,
        privacy: PrivacyService,
    ) -> None:
        self.context = context
        self.privacy = privacy

    def export_local_data(self, workspace_id: str) -> dict[str, Any]:
        return self.privacy.export_workspace(workspace_id)

    def export_local_file(self, workspace_id: str | None = None):
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.export_workspace_to_file(workspace.workspace_id)

    def preview_delete(
        self,
        *,
        workspace_id: str | None = None,
        scope: str,
    ) -> DeletionPreview:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.preview_delete(
            workspace_id=workspace.workspace_id,
            scope=scope,
        )

    def confirm_delete(
        self,
        *,
        workspace_id: str | None = None,
        scope: str,
        confirmation_token: str,
    ) -> DeletionResult:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.confirm_delete(
            workspace_id=workspace.workspace_id,
            scope=scope,
            confirmation_token=confirmation_token,
        )
