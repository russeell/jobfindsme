from __future__ import annotations

import json

from jobfindsme.cli import run
from jobfindsme.storage import Database


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
    from jobfindsme.app import jobfindsmecore

    jobfindsmecore(database).configure_search(
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )
    imported = invoke(
        database,
        capsys,
        "jobs",
        "import",
        str(jobs_file),
    )
    assert imported["unique"] == 1

    matches = invoke(
        database,
        capsys,
        "jobs",
        "search",
    )
    assert matches[0]["job"]["external_id"] == "job-1"
    job_id = matches[0]["job"]["job_id"]

    state = invoke(
        database,
        capsys,
        "state",
        "set",
        "--job",
        job_id,
        "--state",
        "saved",
    )
    assert state["state"] == "saved"
    invoke(
        database,
        capsys,
        "state",
        "set",
        "--job",
        job_id,
        "--state",
        "applied",
    )
    with Database(database).connect() as connection:
        events = connection.execute(
            """
            SELECT previous_state, new_state FROM job_state_events
            ORDER BY created_at, event_id
            """
        ).fetchall()
    assert [(row["previous_state"], row["new_state"]) for row in events] == [
        (None, "saved"),
        ("saved", "applied"),
    ]

    exported = invoke(
        database,
        capsys,
        "export",
    )
    assert exported["job_states"][0]["state"] == "applied"
    assert [
        (event["previous_state"], event["new_state"])
        for event in exported["job_state_events"]
    ] == [(None, "saved"), ("saved", "applied")]

    preview = invoke(
        database,
        capsys,
        "delete",
        "preview",
        "--scope",
        "jobs",
    )
    result = invoke(
        database,
        capsys,
        "delete",
        "confirm",
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
                "doctor",
            ]
        )
        == 0
    )
    assert "**" in capsys.readouterr().out
