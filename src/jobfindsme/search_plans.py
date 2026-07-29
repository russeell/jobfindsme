from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from jobfindsme.contracts import EmploymentType, RecruitmentTrack, SearchPlan
from jobfindsme.storage import Database

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


class SearchPlanNotFoundError(LookupError):
    pass


class SearchPlanService:
    def __init__(
        self,
        database: Database,
        *,
        clock: Clock = lambda: datetime.now(UTC),
        id_factory: IdFactory = lambda: f"plan_{uuid4().hex}",
    ) -> None:
        self.database = database
        self.clock = clock
        self.id_factory = id_factory

    def create(
        self,
        *,
        workspace_id: str,
        name: str,
        target_roles: Sequence[str],
        locations: Sequence[str] = (),
        salary_min_k: int | None = None,
        salary_max_k: int | None = None,
        experience_min_years: int | None = None,
        experience_max_years: int | None = None,
        recruitment_track: str | None = None,
        employment_type: str | None = None,
        official_sources_only: bool = True,
        exclusions: Sequence[str] = (),
    ) -> SearchPlan:
        now = self.clock()
        plan = SearchPlan(
            plan_id=self.id_factory(),
            workspace_id=workspace_id,
            name=name.strip(),
            target_roles=tuple(
                value.strip() for value in target_roles if value.strip()
            ),
            locations=tuple(value.strip() for value in locations if value.strip()),
            salary_min_k=salary_min_k,
            salary_max_k=salary_max_k,
            experience_min_years=experience_min_years,
            experience_max_years=experience_max_years,
            recruitment_track=(
                RecruitmentTrack(recruitment_track) if recruitment_track else None
            ),
            employment_type=(
                EmploymentType(employment_type) if employment_type else None
            ),
            official_sources_only=official_sources_only,
            exclusions=tuple(value.strip() for value in exclusions if value.strip()),
            created_at=now,
            updated_at=now,
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO search_plans (
                    plan_id, workspace_id, name, target_roles_json,
                    locations_json, salary_min_k, salary_max_k,
                    experience_min_years, experience_max_years,
                    recruitment_track, employment_type,
                    official_sources_only, exclusions_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.plan_id,
                    plan.workspace_id,
                    plan.name,
                    json.dumps(plan.target_roles, ensure_ascii=False),
                    json.dumps(plan.locations, ensure_ascii=False),
                    plan.salary_min_k,
                    plan.salary_max_k,
                    plan.experience_min_years,
                    plan.experience_max_years,
                    plan.recruitment_track.value if plan.recruitment_track else None,
                    plan.employment_type.value if plan.employment_type else None,
                    int(plan.official_sources_only),
                    json.dumps(plan.exclusions, ensure_ascii=False),
                    plan.created_at.isoformat(),
                    plan.updated_at.isoformat(),
                ),
            )
        return plan

    def list(self, workspace_id: str) -> list[SearchPlan]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM search_plans
                WHERE workspace_id = ?
                ORDER BY created_at, plan_id
                """,
                (workspace_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(
        self,
        *,
        workspace_id: str,
        plan_id: str,
        name: str,
        target_roles: Sequence[str],
        locations: Sequence[str] = (),
        salary_min_k: int | None = None,
        salary_max_k: int | None = None,
        experience_min_years: int | None = None,
        experience_max_years: int | None = None,
        recruitment_track: str | None = None,
        employment_type: str | None = None,
        official_sources_only: bool = True,
        exclusions: Sequence[str] = (),
    ) -> SearchPlan:
        existing = self.get(workspace_id=workspace_id, plan_id=plan_id)
        plan = SearchPlan(
            plan_id=existing.plan_id,
            workspace_id=existing.workspace_id,
            name=name.strip(),
            target_roles=tuple(
                value.strip() for value in target_roles if value.strip()
            ),
            locations=tuple(value.strip() for value in locations if value.strip()),
            salary_min_k=salary_min_k,
            salary_max_k=salary_max_k,
            experience_min_years=experience_min_years,
            experience_max_years=experience_max_years,
            recruitment_track=(
                RecruitmentTrack(recruitment_track) if recruitment_track else None
            ),
            employment_type=(
                EmploymentType(employment_type) if employment_type else None
            ),
            official_sources_only=official_sources_only,
            exclusions=tuple(value.strip() for value in exclusions if value.strip()),
            created_at=existing.created_at,
            updated_at=self.clock(),
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE search_plans SET
                    name = ?, target_roles_json = ?, locations_json = ?,
                    salary_min_k = ?, salary_max_k = ?,
                    experience_min_years = ?, experience_max_years = ?,
                    recruitment_track = ?, employment_type = ?,
                    official_sources_only = ?, exclusions_json = ?, updated_at = ?
                WHERE workspace_id = ? AND plan_id = ?
                """,
                (
                    plan.name,
                    json.dumps(plan.target_roles, ensure_ascii=False),
                    json.dumps(plan.locations, ensure_ascii=False),
                    plan.salary_min_k,
                    plan.salary_max_k,
                    plan.experience_min_years,
                    plan.experience_max_years,
                    plan.recruitment_track.value if plan.recruitment_track else None,
                    plan.employment_type.value if plan.employment_type else None,
                    int(plan.official_sources_only),
                    json.dumps(plan.exclusions, ensure_ascii=False),
                    plan.updated_at.isoformat(),
                    workspace_id,
                    plan_id,
                ),
            )
        return plan

    def get(self, *, workspace_id: str, plan_id: str) -> SearchPlan:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM search_plans
                WHERE workspace_id = ? AND plan_id = ?
                """,
                (workspace_id, plan_id),
            ).fetchone()
        if row is None:
            raise SearchPlanNotFoundError(plan_id)
        return self._from_row(row)

    @staticmethod
    def _from_row(row: object) -> SearchPlan:
        return SearchPlan(
            plan_id=row["plan_id"],
            workspace_id=row["workspace_id"],
            name=row["name"],
            target_roles=tuple(json.loads(row["target_roles_json"])),
            locations=tuple(json.loads(row["locations_json"])),
            salary_min_k=row["salary_min_k"],
            salary_max_k=row["salary_max_k"],
            experience_min_years=row["experience_min_years"],
            experience_max_years=row["experience_max_years"],
            recruitment_track=(
                RecruitmentTrack(row["recruitment_track"])
                if row["recruitment_track"]
                else None
            ),
            employment_type=(
                EmploymentType(row["employment_type"])
                if row["employment_type"]
                else None
            ),
            official_sources_only=bool(row["official_sources_only"]),
            exclusions=tuple(json.loads(row["exclusions_json"])),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
