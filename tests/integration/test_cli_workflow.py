from __future__ import annotations

import json

from jobfindsme.cli import run


def invoke(database, capsys, *arguments: str):
    assert run(["--db", str(database), *arguments]) == 0
    return json.loads(capsys.readouterr().out)


def test_cli_job_discovery_state_export_and_delete_workflow(tmp_path, capsys) -> None:
    database = tmp_path / "jobfindsme.db"
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        """
        [{
          "id": "job-1",
          "title": "AI应用工程师",
          "company": "示例科技",
          "location": "杭州",
          "description": "Python RAG Agent，1-3年，25-40K",
          "url": "https://example.com/jobs/1"
        }]
        """,
        encoding="utf-8",
    )
    workspace = invoke(
        database,
        capsys,
        "workspace",
        "init",
        "--name",
        "求职",
    )
    plan = invoke(
        database,
        capsys,
        "plan",
        "add",
        "--workspace",
        workspace["workspace_id"],
        "--name",
        "杭州AI",
        "--role",
        "AI应用工程师",
        "--city",
        "杭州",
    )
    imported = invoke(
        database,
        capsys,
        "jobs",
        "import",
        "--workspace",
        workspace["workspace_id"],
        str(jobs_file),
    )
    assert imported["unique"] == 1

    matches = invoke(
        database,
        capsys,
        "jobs",
        "search",
        "--workspace",
        workspace["workspace_id"],
        "--plan",
        plan["plan_id"],
    )
    assert matches[0]["job"]["external_id"] == "job-1"
    job_id = matches[0]["job"]["job_id"]

    state = invoke(
        database,
        capsys,
        "state",
        "set",
        "--workspace",
        workspace["workspace_id"],
        "--job",
        job_id,
        "--state",
        "saved",
    )
    assert state["state"] == "saved"

    exported = invoke(
        database,
        capsys,
        "export",
        "--workspace",
        workspace["workspace_id"],
    )
    assert exported["job_states"][0]["state"] == "saved"

    preview = invoke(
        database,
        capsys,
        "delete",
        "preview",
        "--workspace",
        workspace["workspace_id"],
        "--scope",
        "jobs",
    )
    result = invoke(
        database,
        capsys,
        "delete",
        "confirm",
        "--workspace",
        workspace["workspace_id"],
        "--scope",
        "jobs",
        "--token",
        preview["confirmation_token"],
    )
    assert result["deleted"] is True


def test_cli_supports_markdown_output(tmp_path, capsys) -> None:
    assert (
        run(
            [
                "--db",
                str(tmp_path / "jobfindsme.db"),
                "--output",
                "markdown",
                "workspace",
                "init",
                "--name",
                "My Search",
            ]
        )
        == 0
    )
    assert "**workspace_id**" in capsys.readouterr().out
