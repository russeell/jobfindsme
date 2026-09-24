from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from jobfindsme.context import ActiveContextService
from jobfindsme.profiles.models import (
    CandidateProfile,
    FactStatus,
    FactType,
    ProfileFact,
    ProfileStatus,
    ProfileSummary,
    ResumeImportMode,
    ResumeVersion,
    SourceDocument,
)
from jobfindsme.profiles.parser import DeterministicResumeParser, ResumeTextExtractor
from jobfindsme.storage import Database


class ProfileError(ValueError):
    pass


class ProfileNotFoundError(LookupError):
    pass


class ResumeProfileService:
    def __init__(
        self,
        database: Database,
        *,
        data_root: str | Path | None = None,
        extractor: ResumeTextExtractor | None = None,
        parser: DeterministicResumeParser | None = None,
    ) -> None:
        self.database = database
        self.data_root = (
            Path(data_root).expanduser()
            if data_root is not None
            else database.path.parent
        )
        self.extractor = extractor or ResumeTextExtractor()
        self.parser = parser or DeterministicResumeParser()

    def import_resume(
        self,
        *,
        workspace_id: str,
        source_path: str | Path,
        mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE,
    ) -> CandidateProfile:
        self.database.migrate()
        source = Path(source_path).expanduser().resolve(strict=True)
        extracted = self.extractor.extract_path(source)
        content_hash = hashlib.sha256(extracted.content).hexdigest()
        document_id = _stable_id(
            "document",
            f"{workspace_id}\0{content_hash}\0{self.parser.version}",
        )
        profile_id = _stable_id(
            "profile",
            f"{workspace_id}\0{document_id}\0{self.parser.version}",
        )

        existing = self._find_existing_profile(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if existing is not None:
            if existing.status is ProfileStatus.DRAFT:
                self._set_active_draft(
                    workspace_id=workspace_id,
                    profile_id=existing.profile_id,
                )
            return existing

        parsed = self.parser.parse(extracted.text)
        if not parsed:
            raise ProfileError("no supported profile facts found")

        managed_path = None
        source_reference = None
        if mode is ResumeImportMode.REFERENCE:
            source_reference = str(source)
        elif mode is ResumeImportMode.MANAGED:
            managed_path = str(
                self._write_managed_copy(
                    document_id=document_id,
                    suffix=source.suffix.lower(),
                    content=extracted.content,
                )
            )

        created_at = datetime.now(UTC)
        document = SourceDocument(
            document_id=document_id,
            workspace_id=workspace_id,
            file_name=extracted.file_name,
            media_type=extracted.media_type,
            content_hash=content_hash,
            import_mode=mode,
            source_path=source_reference,
            managed_path=managed_path,
            parser_version=self.parser.version,
            created_at=created_at,
        )
        facts = tuple(
            ProfileFact(
                fact_id=_stable_id(
                    "fact",
                    f"{profile_id}\0{fact.fact_type}\0{fact.value}\0"
                    f"{fact.evidence_start}\0{fact.evidence_end}",
                ),
                fact_type=fact.fact_type,
                value=fact.value,
                evidence_snippet=fact.evidence_snippet[:500],
                evidence_start=fact.evidence_start,
                evidence_end=fact.evidence_end,
                status=FactStatus.PROPOSED,
            )
            for fact in parsed
        )
        profile = CandidateProfile(
            profile_id=profile_id,
            workspace_id=workspace_id,
            document_id=document_id,
            status=ProfileStatus.DRAFT,
            parser_version=self.parser.version,
            facts=facts,
            created_at=created_at,
        )
        try:
            self._persist(document, profile)
        except Exception:
            if managed_path is not None:
                Path(managed_path).unlink(missing_ok=True)
            raise
        return profile

    def load_review(
        self,
        *,
        workspace_id: str,
        profile_id: str,
    ) -> CandidateProfile:
        return self._load_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
            confirmed_only=False,
        )

    def confirm_profile(
        self,
        *,
        workspace_id: str,
        profile_id: str,
        accepted_fact_ids: Sequence[str],
        corrections: Mapping[str, str] | None = None,
    ) -> ProfileSummary:
        profile = self.load_review(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )
        known_ids = {fact.fact_id for fact in profile.facts}
        accepted = set(accepted_fact_ids)
        corrections = dict(corrections or {})
        if not accepted:
            raise ProfileError("at least one fact must be confirmed")
        if not accepted <= known_ids:
            raise ProfileError("accepted_fact_ids contains an unknown fact")
        if not corrections.keys() <= accepted:
            raise ProfileError("only accepted facts can be corrected")
        normalized_corrections = {
            fact_id: _normalize_correction(value)
            for fact_id, value in corrections.items()
        }

        confirmed_at = datetime.now(UTC)
        confirmed_values: list[tuple[FactType, str]] = []
        with self.database.connect() as connection:
            for fact in profile.facts:
                status = (
                    FactStatus.CONFIRMED
                    if fact.fact_id in accepted
                    else FactStatus.REJECTED
                )
                current_value = normalized_corrections.get(
                    fact.fact_id,
                    fact.value,
                )
                if status is FactStatus.CONFIRMED:
                    confirmed_values.append((fact.fact_type, current_value))
                connection.execute(
                    """
                    UPDATE profile_facts
                    SET status = ?, current_value = ?
                    WHERE fact_id = ? AND profile_id = ? AND workspace_id = ?
                    """,
                    (
                        status.value,
                        current_value,
                        fact.fact_id,
                        profile_id,
                        workspace_id,
                    ),
                )
            connection.execute(
                """
                UPDATE candidate_profiles
                SET status = 'confirmed', confirmed_at = ?
                WHERE profile_id = ? AND workspace_id = ?
                """,
                (confirmed_at.isoformat(), profile_id, workspace_id),
            )
            self._create_version(
                connection=connection,
                profile=profile,
                facts=confirmed_values,
            )
            connection.execute(
                """
                DELETE FROM active_resume_imports
                WHERE workspace_id = ? AND profile_id = ?
                """,
                (workspace_id, profile_id),
            )
        return self.confirmed_summary(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )

    def current_version(self, *, workspace_id: str) -> ResumeVersion | None:
        self.database.migrate()
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM resume_versions
                WHERE workspace_id = ? AND is_current = 1
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
        return _version_from_row(row) if row is not None else None

    def clear_current(self, *, workspace_id: str) -> None:
        """Stop using the current resume without deleting historical snapshots."""
        self.database.migrate()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE resume_versions SET is_current=0 WHERE workspace_id=? AND is_current=1",
                (workspace_id,),
            )
            connection.execute(
                "DELETE FROM active_resume_imports WHERE workspace_id=?",
                (workspace_id,),
            )

    def active_draft_profile_id(self, *, workspace_id: str) -> str | None:
        self.database.migrate()
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT profile_id FROM active_resume_imports
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        return row["profile_id"] if row is not None else None

    def abandon_active_draft(
        self,
        *,
        workspace_id: str,
        profile_id: str,
    ) -> None:
        with self.database.connect() as connection:
            deleted = connection.execute(
                """
                DELETE FROM active_resume_imports
                WHERE workspace_id = ? AND profile_id = ?
                """,
                (workspace_id, profile_id),
            ).rowcount
        if not deleted:
            raise ProfileNotFoundError(profile_id)

    def _set_active_draft(self, *, workspace_id: str, profile_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO active_resume_imports (
                    workspace_id, profile_id, updated_at
                ) VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, profile_id, datetime.now(UTC).isoformat()),
            )

    def list_versions(self, *, workspace_id: str) -> list[ResumeVersion]:
        self.database.migrate()
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM resume_versions
                WHERE workspace_id = ?
                ORDER BY version_number DESC
                """,
                (workspace_id,),
            ).fetchall()
        return [_version_from_row(row) for row in rows]

    def _create_version(
        self,
        *,
        connection,
        profile: CandidateProfile,
        facts: list[tuple[FactType, str]],
    ) -> None:
        content: dict[str, list[str]] = {
            "basic_information": [],
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
        }
        section_by_type = {
            FactType.EDUCATION: "education",
            FactType.EXPERIENCE: "experience",
            FactType.PROJECT: "projects",
            FactType.SKILL: "skills",
        }
        for fact_type, value in facts:
            content[section_by_type[fact_type]].append(value)

        now = datetime.now(UTC)
        current = connection.execute(
            """
            SELECT version_id, version_number FROM resume_versions
            WHERE workspace_id = ? AND is_current = 1
            """,
            (profile.workspace_id,),
        ).fetchone()
        next_number = connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1
            FROM resume_versions WHERE workspace_id = ?
            """,
            (profile.workspace_id,),
        ).fetchone()[0]
        if current is not None:
            connection.execute(
                "UPDATE resume_versions SET is_current = 0 WHERE version_id = ?",
                (current["version_id"],),
            )
        connection.execute(
            """
            INSERT INTO resume_versions (
                version_id, workspace_id, profile_id, source_document_id,
                parent_version_id, version_number, content_json,
                is_current, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                f"resume_version_{uuid4().hex}",
                profile.workspace_id,
                profile.profile_id,
                profile.document_id,
                current["version_id"] if current is not None else None,
                next_number,
                json.dumps(content, ensure_ascii=False),
                now.isoformat(),
            ),
        )

    def confirmed_summary(
        self,
        *,
        workspace_id: str,
        profile_id: str,
    ) -> ProfileSummary:
        profile = self._load_profile(
            workspace_id=workspace_id,
            profile_id=profile_id,
            confirmed_only=True,
        )
        return ProfileSummary(
            profile_id=profile.profile_id,
            workspace_id=profile.workspace_id,
            facts=profile.facts,
        )

    def latest_confirmed_summary(
        self,
        *,
        workspace_id: str,
    ) -> ProfileSummary | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT profile_id FROM candidate_profiles
                WHERE workspace_id = ? AND status = 'confirmed'
                ORDER BY confirmed_at DESC, created_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return self.confirmed_summary(
            workspace_id=workspace_id,
            profile_id=row["profile_id"],
        )

    def load_document(
        self,
        *,
        workspace_id: str,
        document_id: str,
    ) -> SourceDocument:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM source_documents
                WHERE workspace_id = ? AND document_id = ?
                """,
                (workspace_id, document_id),
            ).fetchone()
        if row is None:
            raise ProfileNotFoundError(document_id)
        return SourceDocument(
            document_id=row["document_id"],
            workspace_id=row["workspace_id"],
            file_name=row["file_name"],
            media_type=row["media_type"],
            content_hash=row["content_hash"],
            import_mode=row["import_mode"],
            source_path=row["source_path"],
            managed_path=row["managed_path"],
            parser_version=row["parser_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _find_existing_profile(
        self,
        *,
        workspace_id: str,
        document_id: str,
    ) -> CandidateProfile | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT profile_id
                FROM candidate_profiles
                WHERE workspace_id = ? AND document_id = ?
                """,
                (workspace_id, document_id),
            ).fetchone()
        if row is None:
            return None
        return self.load_review(
            workspace_id=workspace_id,
            profile_id=row["profile_id"],
        )

    def _load_profile(
        self,
        *,
        workspace_id: str,
        profile_id: str,
        confirmed_only: bool,
    ) -> CandidateProfile:
        with self.database.connect() as connection:
            profile_row = connection.execute(
                """
                SELECT *
                FROM candidate_profiles
                WHERE workspace_id = ? AND profile_id = ?
                """,
                (workspace_id, profile_id),
            ).fetchone()
            if profile_row is None:
                raise ProfileNotFoundError(profile_id)
            if confirmed_only and profile_row["status"] != "confirmed":
                raise ProfileError("profile is not confirmed")

            fact_query = """
                SELECT *
                FROM profile_facts
                WHERE workspace_id = ? AND profile_id = ?
            """
            parameters: list[str] = [workspace_id, profile_id]
            if confirmed_only:
                fact_query += " AND status = 'confirmed'"
            fact_query += " ORDER BY rowid"
            fact_rows = connection.execute(fact_query, parameters).fetchall()

        facts = tuple(
            ProfileFact(
                fact_id=row["fact_id"],
                fact_type=FactType(row["fact_type"]),
                value=row["current_value"],
                evidence_snippet=row["evidence_snippet"],
                evidence_start=row["evidence_start"],
                evidence_end=row["evidence_end"],
                status=FactStatus(row["status"]),
            )
            for row in fact_rows
        )
        return CandidateProfile(
            profile_id=profile_row["profile_id"],
            workspace_id=profile_row["workspace_id"],
            document_id=profile_row["document_id"],
            status=ProfileStatus(profile_row["status"]),
            parser_version=profile_row["parser_version"],
            facts=facts,
            created_at=datetime.fromisoformat(profile_row["created_at"]),
            confirmed_at=(
                datetime.fromisoformat(profile_row["confirmed_at"])
                if profile_row["confirmed_at"]
                else None
            ),
        )

    def _persist(
        self,
        document: SourceDocument,
        profile: CandidateProfile,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_documents (
                    document_id, workspace_id, file_name, media_type,
                    content_hash, import_mode, source_path, managed_path,
                    parser_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    document.workspace_id,
                    document.file_name,
                    document.media_type,
                    document.content_hash,
                    document.import_mode.value,
                    document.source_path,
                    document.managed_path,
                    document.parser_version,
                    document.created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO candidate_profiles (
                    profile_id, workspace_id, document_id, status,
                    parser_version, created_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    profile.profile_id,
                    profile.workspace_id,
                    profile.document_id,
                    profile.status.value,
                    profile.parser_version,
                    profile.created_at.isoformat(),
                ),
            )
            for fact in profile.facts:
                connection.execute(
                    """
                    INSERT INTO profile_facts (
                        fact_id, profile_id, workspace_id, fact_type,
                        original_value, current_value, evidence_snippet,
                        evidence_start, evidence_end, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact.fact_id,
                        profile.profile_id,
                        profile.workspace_id,
                        fact.fact_type.value,
                        fact.value,
                        fact.value,
                        fact.evidence_snippet,
                        fact.evidence_start,
                        fact.evidence_end,
                        fact.status.value,
                    ),
                )
            connection.execute(
                """
                INSERT INTO active_resume_imports (
                    workspace_id, profile_id, updated_at
                ) VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.workspace_id,
                    profile.profile_id,
                    profile.created_at.isoformat(),
                ),
            )

    def _write_managed_copy(
        self,
        *,
        document_id: str,
        suffix: str,
        content: bytes,
    ) -> Path:
        directory = self.data_root / "documents" / "managed"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        destination = directory / f"{document_id}{suffix}"
        destination.write_bytes(content)
        os.chmod(destination, 0o600)
        return destination


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{uuid5(NAMESPACE_URL, value).hex}"


def _normalize_correction(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ProfileError("corrected fact cannot be empty")
    if len(normalized) > 2000:
        raise ProfileError("corrected fact is too long")
    return normalized


def _version_from_row(row) -> ResumeVersion:
    content = json.loads(row["content_json"])
    return ResumeVersion(
        version_id=row["version_id"],
        workspace_id=row["workspace_id"],
        profile_id=row["profile_id"],
        source_document_id=row["source_document_id"],
        parent_version_id=row["parent_version_id"],
        version_number=row["version_number"],
        content={key: tuple(values) for key, values in content.items()},
        is_current=bool(row["is_current"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class ProfileUseCase:
    def __init__(
        self,
        *,
        context: ActiveContextService,
        profiles: ResumeProfileService,
    ) -> None:
        self.context = context
        self.profiles = profiles

    def import_resume(
        self,
        *,
        workspace_id: str | None = None,
        source_path: str | Path,
        mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE,
    ) -> CandidateProfile:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.import_resume(
            workspace_id=workspace.workspace_id,
            source_path=source_path,
            mode=mode,
        )

    def confirm_profile(
        self,
        *,
        workspace_id: str | None = None,
        profile_id: str,
        accepted_fact_ids: Sequence[str],
        corrections: Mapping[str, str] | None = None,
    ) -> ProfileSummary:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.confirm_profile(
            workspace_id=workspace.workspace_id,
            profile_id=profile_id,
            accepted_fact_ids=accepted_fact_ids,
            corrections=corrections,
        )

    def review_profile(
        self,
        *,
        profile_id: str,
        workspace_id: str | None = None,
    ) -> CandidateProfile:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.load_review(
            workspace_id=workspace.workspace_id,
            profile_id=profile_id,
        )
