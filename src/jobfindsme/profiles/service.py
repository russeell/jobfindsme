from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from jobfindsme.profiles.models import (
    CandidateProfile,
    FactStatus,
    FactType,
    ProfileFact,
    ProfileStatus,
    ProfileSummary,
    ResumeImportMode,
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
        return self.confirmed_summary(
            workspace_id=workspace_id,
            profile_id=profile_id,
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
