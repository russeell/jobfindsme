import json

from jobfindsme.cli import _select_release_wheel, run
from jobfindsme.core import jobfindsmecore
from jobfindsme.importing.parsers import parse_json


def test_cli_workspace_and_plan_flow(tmp_path, capsys) -> None:
    database = tmp_path / "jobfindsme.db"

    assert (
        run(
            [
                "--db",
                str(database),
                "workspace",
                "init",
                "--name",
                "My Search",
            ]
        )
        == 0
    )
    workspace = json.loads(capsys.readouterr().out)

    assert (
        run(
            [
                "--db",
                str(database),
                "plan",
                "add",
                "--workspace",
                workspace["workspace_id"],
                "--name",
                "杭州 AI",
                "--role",
                "AI应用工程师",
                "--city",
                "杭州",
            ]
        )
        == 0
    )
    created_plan = json.loads(capsys.readouterr().out)

    assert (
        run(
            [
                "--db",
                str(database),
                "plan",
                "list",
                "--workspace",
                workspace["workspace_id"],
            ]
        )
        == 0
    )
    plans = json.loads(capsys.readouterr().out)

    assert plans == [created_plan]


def test_self_update_selects_prebuilt_release_wheel() -> None:
    url = _select_release_wheel(
        {
            "assets": [
                {
                    "name": "jobfindsme-0.2.1-py3-none-any.whl",
                    "browser_download_url": "https://example.com/jobfindsme.whl",
                }
            ]
        }
    )

    assert url == "https://example.com/jobfindsme.whl"


def test_cli_profile_import_needs_no_workspace_and_accepts_facts_by_default(
    tmp_path,
    capsys,
) -> None:
    database = tmp_path / "jobfindsme.db"
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")

    assert (
        run(
            [
                "--db",
                str(database),
                "profile",
                "import",
                str(resume),
            ]
        )
        == 0
    )
    profile = json.loads(capsys.readouterr().out)

    assert profile["facts"]
    core = jobfindsmecore(database)
    assert core.profiles.latest_confirmed_summary(workspace_id=profile["workspace_id"])


def test_cli_markdown_job_search_uses_stable_job_blocks(tmp_path, capsys) -> None:
    database = tmp_path / "jobfindsme.db"
    core = jobfindsmecore(database)
    workspace = core.create_workspace("CLI")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "社会招聘，全职正式岗位，Python RAG Agent，1-3年，25-40K",
                        "location": "杭州",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

    assert (
        run(
            [
                "--db",
                str(database),
                "--output",
                "markdown",
                "jobs",
                "search",
                "--workspace",
                workspace.workspace_id,
                "--plan",
                plan.plan_id,
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    # v0.5: deterministic block = facts + signals + link
    assert output.startswith("1. AI应用工程师｜示例科技｜杭州｜社招｜正式｜")
    assert "技能：" in output
    assert "经验：" in output
    assert output.endswith("   投递链接：https://example.com/jobs/1\n")


def test_cli_markdown_empty_job_search_has_stable_message(tmp_path, capsys) -> None:
    database = tmp_path / "jobfindsme.db"
    core = jobfindsmecore(database)
    workspace = core.create_workspace("CLI")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )

    assert (
        run(
            [
                "--db",
                str(database),
                "--output",
                "markdown",
                "jobs",
                "search",
                "--workspace",
                workspace.workspace_id,
                "--plan",
                plan.plan_id,
            ]
        )
        == 0
    )

    assert capsys.readouterr().out == "未找到符合条件的岗位。\n"
