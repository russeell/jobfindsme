from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from pydantic import Field

from jobfindsme.contracts import StrictModel
from jobfindsme.storage import Database

Clock = Callable[[], datetime]


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
            "profile_facts": [dict(row) for row in facts],
        }

    def preview_delete(self, *, workspace_id: str, scope: str) -> DeletionPreview:
        self._validate_scope(scope)
        counts = self._counts(workspace_id)
        token = secrets.token_urlsafe(32)
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

    @classmethod
    def _validate_scope(cls, scope: str) -> None:
        if scope not in cls.VALID_SCOPES:
            raise ValueError(f"invalid deletion scope: {scope}")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
