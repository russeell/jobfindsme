from datetime import UTC, datetime

import pytest

from jobfindsme.search_plans import SearchPlanNotFoundError, SearchPlanService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def make_services(tmp_path):
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()
    ids = iter(("workspace-1", "workspace-2"))
    workspaces = WorkspaceService(database, id_factory=lambda: next(ids))
    plan_ids = iter(("plan-1", "plan-2", "plan-3"))
    plans = SearchPlanService(
        database,
        clock=lambda: datetime(2026, 7, 28, tzinfo=UTC),
        id_factory=lambda: next(plan_ids),
    )
    return workspaces, plans


def test_workspace_can_hold_multiple_search_plans(tmp_path) -> None:
    workspaces, plans = make_services(tmp_path)
    workspace = workspaces.create()

    first = plans.create(
        workspace_id=workspace.workspace_id,
        name="杭州 AI",
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )
    second = plans.create(
        workspace_id=workspace.workspace_id,
        name="上海 Python",
        target_roles=["Python后端"],
        locations=["上海"],
    )

    assert plans.list(workspace.workspace_id) == [first, second]


def test_plans_are_isolated_between_workspaces(tmp_path) -> None:
    workspaces, plans = make_services(tmp_path)
    first_workspace = workspaces.create("first")
    second_workspace = workspaces.create("second")
    plan = plans.create(
        workspace_id=first_workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )

    assert plans.list(second_workspace.workspace_id) == []
    with pytest.raises(SearchPlanNotFoundError):
        plans.get(
            workspace_id=second_workspace.workspace_id,
            plan_id=plan.plan_id,
        )


def test_deleting_workspace_cascades_only_its_plans(tmp_path) -> None:
    workspaces, plans = make_services(tmp_path)
    first_workspace = workspaces.create("first")
    second_workspace = workspaces.create("second")
    plans.create(
        workspace_id=first_workspace.workspace_id,
        name="first-plan",
        target_roles=["AI"],
    )
    second_plan = plans.create(
        workspace_id=second_workspace.workspace_id,
        name="second-plan",
        target_roles=["Python"],
    )

    with workspaces.database.connect() as connection:
        connection.execute(
            "DELETE FROM workspaces WHERE workspace_id = ?",
            (first_workspace.workspace_id,),
        )

    assert plans.list(first_workspace.workspace_id) == []
    assert plans.list(second_workspace.workspace_id) == [second_plan]
