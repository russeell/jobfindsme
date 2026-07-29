import ast
from pathlib import Path

from jobfindsme.contracts import DiscoverySource
from jobfindsme.core import jobfindsmecore
from jobfindsme.importing.parsers import parse_json


def test_core_composes_workspace_and_plan_use_cases(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
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


def test_core_matches_imported_jobs_without_an_adapter_framework(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("求职")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="杭州AI",
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )
    records = parse_json(
        """
        [{
          "id": "1",
          "title": "AI应用工程师",
          "company": "示例科技",
          "location": "杭州",
          "description": "Python RAG Agent",
          "url": "https://example.com/jobs/1"
        }]
        """,
        source_name="fixture",
    )
    core.job_imports.import_records(workspace.workspace_id, records)

    matches = core.match_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
    )

    assert [match.job.external_id for match in matches] == ["1"]


def test_core_configures_and_reuses_active_search_without_ids(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")

    first = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海"],
    )
    second = core.configure_search(
        target_roles=["RAG工程师"],
        locations=["杭州"],
    )

    assert second.workspace.workspace_id == first.workspace.workspace_id
    assert second.plan.plan_id == first.plan.plan_id
    assert second.plan.target_roles == ("RAG工程师",)
    assert isinstance(core.search_jobs(), list)  # may be empty or have live results


def test_core_passes_confirmed_profile_into_matching(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configuration = core.configure_search(target_roles=["AI应用工程师"])
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")
    profile = core.import_resume(source_path=resume)
    core.confirm_profile(
        profile_id=profile.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in profile.facts],
    )
    records = parse_json(
        """
        [
          {
            "id": "python",
            "title": "AI应用工程师",
            "company": "甲公司",
            "description": "Python RAG",
            "url": "https://example.com/python"
          },
          {
            "id": "java",
            "title": "AI应用工程师",
            "company": "乙公司",
            "description": "Java Spring",
            "url": "https://example.com/java"
          }
        ]
        """,
        source_name="fixture",
    )
    core.job_imports.import_records(configuration.workspace.workspace_id, records)

    matches = core.match_jobs()

    assert matches[0].job.external_id == "python"
    assert matches[0].evidence.evidence_pairs


def test_updating_search_constraints_preserves_sources_unless_explicitly_cleared(
    tmp_path,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="本地岗位",
                path=str(tmp_path / "jobs.json"),
            ),
        ),
    )

    updated = core.configure_search(target_roles=["RAG工程师"])
    cleared = core.configure_search(target_roles=["RAG工程师"], sources=())

    assert len(updated.sources) == 1
    assert cleared.sources == ()
    assert updated.plan.plan_id == configured.plan.plan_id
