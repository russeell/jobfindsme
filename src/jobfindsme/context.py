from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from jobfindsme.contracts import SearchPlan, Workspace
from jobfindsme.search_plans import SearchPlanService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


@dataclass(frozen=True)
class ResolvedContext:
    workspace: Workspace
    plan: SearchPlan | None


class ActiveContextService:
    """Hide internal IDs while preserving explicit multi-workspace control."""

    def __init__(
        self,
        database: Database,
        workspaces: WorkspaceService,
        plans: SearchPlanService,
    ) -> None:
        self.database = database
        self.workspaces = workspaces
        self.plans = plans

    def resolve_workspace(self, workspace_id: str | None = None) -> Workspace:
        if workspace_id:
            workspace = self.workspaces.get(workspace_id)
            self.activate(workspace_id=workspace.workspace_id)
            return workspace

        active_workspace_id, _ = self._active_ids()
        if active_workspace_id:
            try:
                return self.workspaces.get(active_workspace_id)
            except LookupError:
                pass

        existing = self.workspaces.list()
        workspace = existing[0] if existing else self.workspaces.create("jobfindsme")
        self.activate(workspace_id=workspace.workspace_id)
        return workspace

    def resolve(
        self,
        *,
        workspace_id: str | None = None,
        plan_id: str | None = None,
        require_plan: bool = True,
    ) -> ResolvedContext:
        workspace = self.resolve_workspace(workspace_id)
        selected_plan_id = plan_id
        active_workspace_id, active_plan_id = self._active_ids()
        if selected_plan_id is None and active_workspace_id == workspace.workspace_id:
            selected_plan_id = active_plan_id

        plan = None
        if selected_plan_id:
            try:
                plan = self.plans.get(
                    workspace_id=workspace.workspace_id,
                    plan_id=selected_plan_id,
                )
            except LookupError:
                if plan_id:
                    raise
        if plan is None:
            plans = self.plans.list(workspace.workspace_id)
            plan = plans[-1] if plans else None
        if require_plan and plan is None:
            raise ValueError(
                "search is not configured; "
                "run setup (with target_roles) before searching"
            )
        self.activate(
            workspace_id=workspace.workspace_id,
            plan_id=plan.plan_id if plan else None,
        )
        return ResolvedContext(workspace=workspace, plan=plan)

    def activate(self, *, workspace_id: str, plan_id: str | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO active_context (
                    singleton, workspace_id, plan_id, updated_at
                ) VALUES (1, ?, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    workspace_id = excluded.workspace_id,
                    plan_id = CASE
                        WHEN active_context.workspace_id = excluded.workspace_id
                        THEN COALESCE(excluded.plan_id, active_context.plan_id)
                        ELSE excluded.plan_id
                    END,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, plan_id, datetime.now(UTC).isoformat()),
            )

    def _active_ids(self) -> tuple[str | None, str | None]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT workspace_id, plan_id FROM active_context WHERE singleton = 1"
            ).fetchone()
        if row is None:
            return None, None
        return row["workspace_id"], row["plan_id"]
