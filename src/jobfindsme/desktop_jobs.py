"""Stable desktop job snapshots and explicit user tracking events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from jobfindsme.contracts import EmploymentType, JobPosting, RecruitmentTrack
from jobfindsme.desktop_rules import DEFAULT_WEIGHTS, evaluate
from jobfindsme.importing.repository import JobRepository
from jobfindsme.storage import Database
from jobfindsme.taxonomy import extract_skills

UnknownPolicy = Literal["include", "exclude", "only"]
ReadFilter = Literal["any", "read", "unread"]
SalaryMode = Literal["overlap", "contained"]

LEGACY_WEIGHTS = {
    "responsibilities": 35,
    "skills": 30,
    "projects": 25,
    "bonus": 10,
}


@dataclass(frozen=True)
class DesktopJobFilters:
    cities: tuple[str, ...] = ()
    salary_min_k: int | None = None
    salary_max_k: int | None = None
    salary_mode: SalaryMode = "overlap"
    recruitment_track: str | None = None
    employment_type: str | None = None
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    source_names: tuple[str, ...] = ()
    read: ReadFilter = "any"
    unknown_policy: UnknownPolicy = "include"

    def validate(self) -> None:
        if self.salary_mode not in {"overlap", "contained"}:
            raise ValueError("salary_mode must be overlap or contained")
        if self.unknown_policy not in {"include", "exclude", "only"}:
            raise ValueError("unknown_policy must be include, exclude, or only")
        if self.read not in {"any", "read", "unread"}:
            raise ValueError("read filter must be any, read, or unread")
        for low, high, label in (
            (self.salary_min_k, self.salary_max_k, "salary"),
            (self.experience_min_years, self.experience_max_years, "experience"),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError(f"{label} minimum cannot exceed maximum")


@dataclass(frozen=True)
class JobTrackingState:
    read: bool = False
    saved: bool = False
    applied: bool = False


class DesktopJobService:
    def __init__(self, database: Database, jobs: JobRepository) -> None:
        self.database = database
        self.jobs = jobs

    def create_snapshot(
        self,
        *,
        workspace_id: str,
        intent: str,
        job_ids: list[str],
        resume_version,
        filters: DesktopJobFilters,
        weights: dict[str, int] | None = None,
        rule_version_id: str | None = None,
    ) -> str:
        filters.validate()
        if rule_version_id is None and weights is None:
            rule_version_id = self.active_rule(workspace_id)
        if rule_version_id is not None:
            if weights is not None:
                raise ValueError("weights and rule_version_id are mutually exclusive")
            normalized_weights = self.weights_for_rule(
                workspace_id=workspace_id, rule_version_id=rule_version_id
            )
        else:
            normalized_weights = self._validate_weights(weights or DEFAULT_WEIGHTS)
            rule_version_id = self._ensure_rule_version(
                workspace_id, normalized_weights
            )
        read_ids = self._read_job_ids(workspace_id)
        unique_jobs: list[JobPosting] = []
        for job_id in dict.fromkeys(job_ids):
            try:
                unique_jobs.append(
                    self.jobs.get(workspace_id=workspace_id, job_id=job_id)
                )
            except LookupError:
                continue
        eligible = [
            job
            for job in unique_jobs
            if self._matches(job, filters=filters, read_ids=read_ids)
        ]
        score_payload: dict[str, dict] = {}
        ranked: list[tuple[float, str]] = []
        for job in eligible:
            score, components, coverage = self._score(
                job,
                intent=intent,
                resume_version=resume_version,
                weights=normalized_weights,
            )
            score_payload[job.job_id] = {
                "score": score,
                "components": components,
                "coverage": coverage,
            }
            if set(normalized_weights) == set(DEFAULT_WEIGHTS):
                score_payload[job.job_id] = evaluate(
                    job, resume_version, normalized_weights
                )
            ranked.append((score, job.job_id))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        ordered_ids = [job_id for _score, job_id in ranked]
        run_id = f"search_{uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO desktop_search_runs (
                    run_id, workspace_id, resume_version_id, rule_version_id,
                    intent, filter_snapshot_json, ordered_job_ids_json,
                    scores_json, created_at, candidate_job_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    workspace_id,
                    resume_version.version_id if resume_version else None,
                    rule_version_id,
                    intent,
                    json.dumps(asdict(filters), ensure_ascii=False, sort_keys=True),
                    json.dumps(ordered_ids),
                    json.dumps(score_payload, ensure_ascii=False, sort_keys=True),
                    now,
                    json.dumps([job.job_id for job in unique_jobs]),
                ),
            )
        return run_id

    def ensure_rule_version(
        self, workspace_id: str, weights: dict[str, int] | None = None
    ) -> str:
        """Return the immutable scoring snapshot used by a scheduled task."""

        return (
            self.active_rule(workspace_id) if weights is None else None
        ) or self._ensure_rule_version(
            workspace_id, self._validate_weights(weights or DEFAULT_WEIGHTS)
        )

    def active_rule(self, workspace_id: str) -> str | None:
        with self.database.connect() as db:
            row = db.execute(
                (
                    "SELECT rule_version_id FROM active_match"
                    "ing_rules WHERE workspace_id=?"
                ),
                (workspace_id,),
            ).fetchone()
        return row[0] if row else None

    def weights_for_rule(
        self, *, workspace_id: str, rule_version_id: str
    ) -> dict[str, int]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT weights_json FROM scoring_rule_versions "
                "WHERE workspace_id = ? AND rule_version_id = ?",
                (workspace_id, rule_version_id),
            ).fetchone()
        if row is None:
            raise ValueError("scoring rule version does not belong to this workspace")
        return self._validate_weights(json.loads(row["weights_json"]))

    def page(
        self, *, workspace_id: str, run_id: str, page: int, page_size: int
    ) -> dict:
        if page < 1:
            raise ValueError("page must be at least 1")
        if page_size not in {10, 20, 50}:
            raise ValueError("page_size must be 10, 20, or 50")
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM desktop_search_runs
                WHERE run_id = ? AND workspace_id = ?
                """,
                (run_id, workspace_id),
            ).fetchone()
        if row is None:
            raise LookupError(run_id)
        ordered_ids = json.loads(row["ordered_job_ids_json"])
        scores = json.loads(row["scores_json"])
        start = (page - 1) * page_size
        selected_ids = ordered_ids[start : start + page_size]
        states = self.tracking_states(workspace_id, selected_ids)
        items = []
        for job_id in selected_ids:
            job = self.jobs.get(workspace_id=workspace_id, job_id=job_id)
            items.append(
                {
                    "job": job.model_dump(mode="json"),
                    **scores[job_id],
                    "tracking": asdict(states.get(job_id, JobTrackingState())),
                }
            )
        total = len(ordered_ids)
        return {
            "run_id": run_id,
            "resume_version_id": row["resume_version_id"],
            "rule_version_id": row["rule_version_id"],
            "page": page,
            "page_size": page_size,
            "total": total,
            "page_count": (total + page_size - 1) // page_size,
            "items": items,
            "rerank": json.loads(row["rerank_json"]) if row["rerank_json"] else None,
        }

    def set_tracking(
        self,
        *,
        workspace_id: str,
        job_id: str,
        event_type: Literal["read", "saved", "applied", "apply_opened"],
        enabled: bool = True,
    ) -> JobTrackingState:
        self.jobs.get(workspace_id=workspace_id, job_id=job_id)
        now = datetime.now(UTC).isoformat()
        event_id = f"tracking_{uuid4().hex}"
        with self.database.connect() as connection:
            if event_type == "read":
                connection.execute(
                    """
                    INSERT INTO job_read_events (
                        event_id, workspace_id, job_id, event_type, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        workspace_id,
                        job_id,
                        "read" if enabled else "unread",
                        now,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO job_tracking_events (
                        event_id, workspace_id, job_id, event_type, enabled, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, workspace_id, job_id, event_type, int(enabled), now),
                )
                if event_type in {"saved", "applied"}:
                    connection.execute(
                        """
                        INSERT INTO job_tracking_flags (
                            workspace_id, job_id, saved, applied, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(workspace_id, job_id) DO UPDATE SET
                            saved = CASE WHEN ? = 'saved'
                                THEN excluded.saved ELSE job_tracking_flags.saved END,
                            applied = CASE WHEN ? = 'applied'
                                THEN excluded.applied
                                ELSE job_tracking_flags.applied END,
                            updated_at = excluded.updated_at
                        """,
                        (
                            workspace_id,
                            job_id,
                            int(enabled) if event_type == "saved" else 0,
                            int(enabled) if event_type == "applied" else 0,
                            now,
                            event_type,
                            event_type,
                        ),
                    )
        return self.tracking_states(workspace_id, [job_id])[job_id]

    def tracking_states(
        self, workspace_id: str, job_ids: list[str]
    ) -> dict[str, JobTrackingState]:
        if not job_ids:
            return {}
        placeholders = ",".join("?" for _ in job_ids)
        with self.database.connect() as connection:
            flag_rows = connection.execute(
                f"""
                SELECT job_id, saved, applied FROM job_tracking_flags
                WHERE workspace_id = ? AND job_id IN ({placeholders})
                """,
                (workspace_id, *job_ids),
            ).fetchall()
            read_rows = connection.execute(
                f"""
                SELECT r.job_id, r.event_type FROM job_read_events r
                JOIN (
                    SELECT job_id, MAX(created_at || event_id) AS latest
                    FROM job_read_events
                    WHERE workspace_id = ? AND job_id IN ({placeholders})
                    GROUP BY job_id
                ) latest ON latest.job_id = r.job_id
                          AND latest.latest = r.created_at || r.event_id
                WHERE r.workspace_id = ?
                """,
                (workspace_id, *job_ids, workspace_id),
            ).fetchall()
        flags = {
            row["job_id"]: (bool(row["saved"]), bool(row["applied"]))
            for row in flag_rows
        }
        reads = {row["job_id"]: row["event_type"] == "read" for row in read_rows}
        return {
            job_id: JobTrackingState(
                read=reads.get(job_id, False),
                saved=flags.get(job_id, (False, False))[0],
                applied=flags.get(job_id, (False, False))[1],
            )
            for job_id in job_ids
        }

    def list_tracking(self, workspace_id: str) -> list[dict]:
        jobs = self.jobs.list(workspace_id)
        states = self.tracking_states(workspace_id, [job.job_id for job in jobs])
        return [
            {
                "job": job.model_dump(mode="json"),
                "tracking": asdict(states[job.job_id]),
            }
            for job in jobs
            if any(asdict(states[job.job_id]).values())
        ]

    def _read_job_ids(self, workspace_id: str) -> set[str]:
        jobs = self.jobs.list(workspace_id)
        states = self.tracking_states(workspace_id, [job.job_id for job in jobs])
        return {job_id for job_id, state in states.items() if state.read}

    @staticmethod
    def _known_match(known: bool, matches: bool, policy: UnknownPolicy) -> bool:
        if policy == "only":
            return not known
        if not known:
            return policy == "include"
        return matches

    @classmethod
    def _matches(
        cls, job: JobPosting, *, filters: DesktopJobFilters, read_ids: set[str]
    ) -> bool:
        if filters.source_names and job.source.source_name not in filters.source_names:
            return False
        if filters.read == "read" and job.job_id not in read_ids:
            return False
        if filters.read == "unread" and job.job_id in read_ids:
            return False
        if filters.cities:
            known = bool(job.locations)
            matched = any(
                city.casefold() in location.casefold()
                for city in filters.cities
                for location in job.locations
            )
            if not cls._known_match(known, matched, filters.unknown_policy):
                return False
        if filters.recruitment_track:
            known = job.recruitment_track is not RecruitmentTrack.UNKNOWN
            matched = job.recruitment_track.value == filters.recruitment_track
            if not cls._known_match(known, matched, filters.unknown_policy):
                return False
        if filters.employment_type:
            known = job.employment_type is not EmploymentType.UNKNOWN
            matched = job.employment_type.value == filters.employment_type
            if not cls._known_match(known, matched, filters.unknown_policy):
                return False
        if filters.salary_min_k is not None or filters.salary_max_k is not None:
            known = job.salary_min_k is not None and job.salary_max_k is not None
            if filters.salary_mode == "overlap":
                matched = (
                    known
                    and (
                        filters.salary_min_k is None
                        or job.salary_max_k >= filters.salary_min_k
                    )
                    and (
                        filters.salary_max_k is None
                        or job.salary_min_k <= filters.salary_max_k
                    )
                )
            else:
                matched = (
                    known
                    and (
                        filters.salary_min_k is None
                        or job.salary_min_k >= filters.salary_min_k
                    )
                    and (
                        filters.salary_max_k is None
                        or job.salary_max_k <= filters.salary_max_k
                    )
                )
            if not cls._known_match(known, matched, filters.unknown_policy):
                return False
        if (
            filters.experience_min_years is not None
            or filters.experience_max_years is not None
        ):
            known = (
                job.experience_min_years is not None
                and job.experience_max_years is not None
            )
            matched = (
                known
                and (
                    filters.experience_min_years is None
                    or job.experience_max_years >= filters.experience_min_years
                )
                and (
                    filters.experience_max_years is None
                    or job.experience_min_years <= filters.experience_max_years
                )
            )
            if not cls._known_match(known, matched, filters.unknown_policy):
                return False
        return True

    @staticmethod
    def _validate_weights(weights: dict[str, int]) -> dict[str, int]:
        if set(weights) not in (set(DEFAULT_WEIGHTS), set(LEGACY_WEIGHTS)):
            raise ValueError(f"weights must contain {sorted(DEFAULT_WEIGHTS)}")
        if any(type(value) is not int or value < 0 for value in weights.values()):
            raise ValueError("weights must be non-negative integers")
        if sum(weights.values()) != 100:
            raise ValueError("weights must total 100")
        return dict(weights)

    def _ensure_rule_version(self, workspace_id: str, weights: dict[str, int]) -> str:
        encoded = json.dumps(weights, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{workspace_id}:{encoded}".encode()).hexdigest()[:20]
        rule_id = f"rule_{digest}"
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO scoring_rule_versions (
                    rule_version_id, workspace_id, name, weights_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    workspace_id,
                    "desktop-v2"
                    if set(weights) == set(DEFAULT_WEIGHTS)
                    else "desktop-default",
                    encoded,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return rule_id

    @staticmethod
    def _score(job, *, intent: str, resume_version, weights: dict[str, int]):
        if set(weights) == set(DEFAULT_WEIGHTS):
            result = evaluate(job, resume_version, weights)
            return result["score"], result["components"], result["coverage"]
        haystack = f"{job.title} {job.description}".casefold()
        intent_terms = {part.casefold() for part in intent.split() if part}
        responsibilities = (
            1.0 if any(term in haystack for term in intent_terms) else 0.0
        )
        skills = 0.0
        projects = 0.0
        observed = {"responsibilities", "bonus"}
        if resume_version is not None:
            resume_skills = {
                skill.casefold()
                for value in resume_version.content.get("skills", ())
                for skill in extract_skills(value)
            }
            job_skills = {skill.casefold() for skill in extract_skills(haystack)}
            if resume_skills and job_skills:
                skills = len(resume_skills & job_skills) / len(job_skills)
                observed.add("skills")
            project_terms = {
                term.casefold()
                for value in resume_version.content.get("projects", ())
                for term in extract_skills(value)
            }
            if project_terms and job_skills:
                projects = len(project_terms & job_skills) / len(job_skills)
                observed.add("projects")
        component_ratios = {
            "responsibilities": responsibilities,
            "skills": skills,
            "projects": projects,
            "bonus": 1.0 if job.source.liveness.value == "active" else 0.0,
        }
        components = {
            key: round(component_ratios[key] * weight, 2)
            for key, weight in weights.items()
        }
        score = round(sum(components.values()), 2)
        coverage = round(sum(weights[key] for key in observed) / 100, 2)
        return score, components, coverage
