import ast
from pathlib import Path

from jobfindsme.core import JobFindsMeCore


def test_core_composes_workspace_and_plan_use_cases(tmp_path) -> None:
    core = JobFindsMeCore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("My Search")

    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="杭州 AI",
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )

    assert core.list_workspaces() == [workspace]
    assert core.list_search_plans(workspace.workspace_id) == [plan]


def test_core_does_not_import_adapter_frameworks() -> None:
    core_dir = Path(__file__).parents[2] / "src" / "jobfindsme" / "core"
    forbidden = {"fastapi", "mcp", "agents", "flask", "typer", "click"}

    for path in core_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert imports.isdisjoint(forbidden), path
