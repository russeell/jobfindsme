import json
import ssl

from jobfindsme.cli import _fetch_latest_release, _select_release_wheel, run
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


def test_fetch_latest_release_uses_certifi_ssl_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"tag_name": "v0.10.0", "assets": []}).encode()

    def fake_urlopen(request, timeout, context):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["context"] = context
        return FakeResponse()

    monkeypatch.setattr("jobfindsme.cli.urllib.request.urlopen", fake_urlopen)

    release = _fetch_latest_release()

    assert release["tag_name"] == "v0.10.0"
    assert captured["timeout"] == 20
    assert isinstance(captured["context"], ssl.SSLContext)
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert (
        captured["request"].full_url
        == "https://api.github.com/repos/russeell/jobfindsme/releases/latest"
    )


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
                        "description": (
                            "社会招聘，全职正式岗位，Python RAG Agent，1-3年，25-40K"
                        ),
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


def test_cli_markdown_show_match_degree_when_profile_exists(tmp_path, capsys) -> None:
    database = tmp_path / "jobfindsme.db"
    core = jobfindsmecore(database)
    workspace = core.create_workspace("CLI")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG、Agent", encoding="utf-8")
    imported = core.import_resume(source_path=str(resume))
    core.confirm_profile(
        profile_id=imported.profile_id,
        accepted_fact_ids=[f.fact_id for f in imported.facts],
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
                        "description": (
                            "社会招聘，全职正式，Python RAG Agent，1-3年，25-40K"
                        ),
                        "location": "杭州",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="企业官网",
        ),
    )

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

    output = capsys.readouterr().out
    assert "匹配度：" in output  # profile exists → signal score shown
    assert "投递链接：https://example.com/jobs/1" in output
