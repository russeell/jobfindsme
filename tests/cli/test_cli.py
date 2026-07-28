import json

from jobfindsme.cli import run


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
