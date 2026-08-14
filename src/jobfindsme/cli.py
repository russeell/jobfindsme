from __future__ import annotations

import argparse
import dataclasses
import json
import os
import ssl
import sys
import urllib.request
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from jobfindsme.contracts import JobStateKind
from jobfindsme.core import jobfindsmecore
from jobfindsme.doctor import Doctor
from jobfindsme.importing.parsers import parse_csv, parse_json
from jobfindsme.installer import HostInstaller, detect_host
from jobfindsme.presentation import format_job_list
from jobfindsme.profiles.models import ResumeImportMode


def default_database_path() -> Path:
    override = os.getenv("JOBFINDSME_DB_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".jobfindsme" / "data" / "jobfindsme.db"


def _workspace_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobfindsme")
    parser.add_argument("--db", type=Path, default=default_database_path())
    parser.add_argument("--output", choices=("json", "markdown"), default="json")
    parser.add_argument(
        "--version",
        action="version",
        version=f"jobfindsme {_version()}",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    workspace = groups.add_parser("workspace")
    workspace_actions = workspace.add_subparsers(dest="action", required=True)
    workspace_init = workspace_actions.add_parser("init")
    workspace_init.add_argument("--name", default="My Job Search")
    workspace_actions.add_parser("list")

    profile = groups.add_parser("profile")
    profile_actions = profile.add_subparsers(dest="action", required=True)
    profile_import = profile_actions.add_parser("import")
    profile_import.add_argument("--workspace")
    profile_import.add_argument("path", type=Path)
    profile_import.add_argument(
        "--mode",
        choices=tuple(ResumeImportMode),
        default=ResumeImportMode.FORGET_SOURCE,
    )
    profile_import.add_argument(
        "--review",
        action="store_true",
        help="keep parsed facts in draft state instead of accepting them",
    )
    profile_review = profile_actions.add_parser("review")
    _workspace_argument(profile_review)
    profile_review.add_argument("--profile", required=True)
    profile_confirm = profile_actions.add_parser("confirm")
    _workspace_argument(profile_confirm)
    profile_confirm.add_argument("--profile", required=True)
    profile_confirm.add_argument("--fact", action="append", required=True)

    plan = groups.add_parser("plan")
    plan_actions = plan.add_subparsers(dest="action", required=True)
    plan_add = plan_actions.add_parser("add")
    _workspace_argument(plan_add)
    plan_add.add_argument("--name", required=True)
    plan_add.add_argument("--role", action="append", required=True)
    plan_add.add_argument("--city", action="append", default=[])
    plan_add.add_argument("--salary-min-k", type=int)
    plan_add.add_argument("--salary-max-k", type=int)
    plan_add.add_argument(
        "--salary-policy",
        choices=("strict", "include_undisclosed"),
        default="strict",
    )
    plan_add.add_argument("--experience-min-years", type=int)
    plan_add.add_argument("--experience-max-years", type=int)
    plan_add.add_argument("--exclude", action="append", default=[])
    plan_list = plan_actions.add_parser("list")
    _workspace_argument(plan_list)

    jobs = groups.add_parser("jobs")
    job_actions = jobs.add_subparsers(dest="action", required=True)
    job_import = job_actions.add_parser("import")
    _workspace_argument(job_import)
    job_import.add_argument("path", type=Path)
    job_import.add_argument("--source-name", default="local-import")
    job_search = job_actions.add_parser("search")
    _workspace_argument(job_search)
    job_search.add_argument("--plan", required=True)
    job_search.add_argument("--limit", type=int, default=20)

    state = groups.add_parser("state")
    state_actions = state.add_subparsers(dest="action", required=True)
    state_set = state_actions.add_parser("set")
    _workspace_argument(state_set)
    state_set.add_argument("--job", required=True)
    state_set.add_argument("--state", choices=tuple(JobStateKind), required=True)
    state_set.add_argument("--note", default="")
    state_list = state_actions.add_parser("list")
    _workspace_argument(state_list)

    export = groups.add_parser("export")
    # Workspace is an internal concept; export resolves the active one when
    # omitted. Only the MCP delete tool and admin flows expose workspace IDs.
    export.add_argument("--workspace", default=None)
    export.add_argument("--path", type=Path)

    delete = groups.add_parser("delete")
    delete_actions = delete.add_subparsers(dest="action", required=True)
    delete_preview = delete_actions.add_parser("preview")
    _workspace_argument(delete_preview)
    delete_preview.add_argument(
        "--scope", choices=("jobs", "profile", "workspace"), required=True
    )
    delete_confirm = delete_actions.add_parser("confirm")
    _workspace_argument(delete_confirm)
    delete_confirm.add_argument(
        "--scope", choices=("jobs", "profile", "workspace"), required=True
    )
    delete_confirm.add_argument("--token", required=True)

    for action in ("connect", "install", "upgrade", "uninstall"):
        host_action = groups.add_parser(action)
        host_action.add_argument(
            "host",
            nargs="?",
            choices=(
                "codex",
                "claude",
                "cursor",
            ),
        )
        host_action.add_argument("--home", type=Path)
        host_action.add_argument(
            "--path", type=Path, help="custom MCP config path (any agent)"
        )

    groups.add_parser("doctor")
    groups.add_parser("self-update")
    groups.add_parser("config", help="output standard MCP JSON for any agent")
    setup_parser = groups.add_parser("setup")
    setup_parser.add_argument(
        "--platform",
        nargs="+",
        choices=("boss", "liepin"),
    )
    return parser


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("jobfindsme")
    except Exception:
        return "unknown"


def _self_update() -> dict:
    import subprocess

    try:
        release = _fetch_latest_release()
        wheel_url = _select_release_wheel(release)
    except Exception as error:
        return {"ok": False, "output": f"could not resolve latest release: {error}"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            f"jobfindsme[browser] @ {wheel_url}",
        ],
        capture_output=True,
        text=True,
    )
    return {
        "ok": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip(),
    }


def _release_request() -> urllib.request.Request:
    return urllib.request.Request(
        "https://api.github.com/repos/russeell/jobfindsme/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "jobfindsme-updater",
        },
    )


def _ssl_context() -> ssl.SSLContext | None:
    """TLS context pinned to certifi CA roots, or None when unavailable."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _fetch_latest_release() -> dict[str, Any]:
    """Resolve the latest GitHub release, trusting certifi's CA bundle."""
    with urllib.request.urlopen(
        _release_request(), timeout=20, context=_ssl_context()
    ) as response:
        return json.load(response)


def _select_release_wheel(release: dict[str, Any]) -> str:
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if (
            name.startswith("jobfindsme-")
            and name.endswith("-py3-none-any.whl")
            and url
        ):
            return url
    raise ValueError("latest release has no compatible wheel")


def _mcp_json_config() -> dict:
    """Standard MCP JSON — paste into any agent's config file."""
    import sys

    return {
        "mcpServers": {
            "jobfindsme": {
                "command": sys.executable,
                "args": ["-m", "jobfindsme.mcp"],
            }
        }
    }


def _serializable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _serializable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_serializable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return value


def _markdown(value: Any) -> str:
    value = _serializable(value)
    if isinstance(value, list):
        if not value:
            return "_No results_"
        return "\n\n".join(
            f"## {index + 1}\n{_markdown(item)}" for index, item in enumerate(value)
        )
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, dict | list):
                lines.extend([f"### {key}", _markdown(item)])
            else:
                lines.append(f"- **{key}**: {item}")
        return "\n".join(lines)
    return str(value)


def _emit(value: Any, output: str, *, job_list: bool = False) -> None:
    serializable = _serializable(value)
    if output == "markdown":
        if job_list:
            print(format_job_list(value))
        else:
            print(_markdown(serializable))
    else:
        print(json.dumps(serializable, ensure_ascii=False))


def _execute(core: jobfindsmecore, args: argparse.Namespace) -> Any:
    if args.group == "workspace":
        if args.action == "init":
            return core.create_workspace(args.name)
        return core.list_workspaces()
    if args.group == "profile":
        if args.action == "import":
            profile = core.import_resume(
                workspace_id=args.workspace,
                source_path=args.path,
                mode=ResumeImportMode(args.mode),
            )
            if args.review:
                return profile
            return core.confirm_profile(
                workspace_id=args.workspace,
                profile_id=profile.profile_id,
                accepted_fact_ids=[fact.fact_id for fact in profile.facts],
            )
        if args.action == "review":
            return core.profiles.load_review(
                workspace_id=args.workspace,
                profile_id=args.profile,
            )
        return core.confirm_profile(
            workspace_id=args.workspace,
            profile_id=args.profile,
            accepted_fact_ids=args.fact,
        )
    if args.group == "plan":
        if args.action == "add":
            return core.create_search_plan(
                workspace_id=args.workspace,
                name=args.name,
                target_roles=args.role,
                locations=args.city,
                salary_min_k=args.salary_min_k,
                salary_max_k=args.salary_max_k,
                salary_policy=args.salary_policy,
                experience_min_years=args.experience_min_years,
                experience_max_years=args.experience_max_years,
                exclusions=args.exclude,
            )
        return core.list_search_plans(args.workspace)
    if args.group == "jobs":
        if args.action == "import":
            content = args.path.read_text(encoding="utf-8")
            records = (
                parse_csv(content, source_name=args.source_name)
                if args.path.suffix.casefold() == ".csv"
                else parse_json(content, source_name=args.source_name)
            )
            return core.job_imports.import_records(args.workspace, records)
        return core.match_jobs(
            workspace_id=args.workspace,
            plan_id=args.plan,
            limit=args.limit,
        )
    if args.group == "state":
        if args.action == "set":
            return core.update_job_state(
                workspace_id=args.workspace,
                job_id=args.job,
                state=JobStateKind(args.state),
                note=args.note,
            )
        return core.list_job_states(args.workspace)
    if args.group == "export":
        # The workspace is an internal concept — never require it from users.
        workspace_id = args.workspace or core.context.resolve_workspace().workspace_id
        exported = core.export_local_data(workspace_id)
        if args.path:
            args.path.write_text(
                json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return {"exported_to": str(args.path)}
        return exported
    if args.group == "delete":
        if args.action == "preview":
            return core.preview_delete(
                workspace_id=args.workspace,
                scope=args.scope,
            )
        return core.confirm_delete(
            workspace_id=args.workspace,
            scope=args.scope,
            confirmation_token=args.token,
        )
    if args.group == "doctor":
        return Doctor(core.database.path).run()
    raise AssertionError("argparse accepted an unsupported command")


def _prompt_host(candidates: list[str]) -> str | None:
    """Interactive fallback for `jobfindsme connect` when nothing was detected."""
    from jobfindsme.installer import HOST_ORDER

    print("未检测到明确的 Agent 配置，请选择要接入的 Agent：", file=sys.stderr)
    for index, host in enumerate(HOST_ORDER, start=1):
        mark = "（检测到配置）" if host in candidates else ""
        print(f"  {index}) {host} {mark}", file=sys.stderr)
    try:
        choice = input("输入序号: ").strip()
    except EOFError:
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(HOST_ORDER):
        return HOST_ORDER[int(choice) - 1]
    return None


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.group == "self-update":
        result = _self_update()
        _emit(result, args.output)
        return 0 if result["ok"] else 1
    if args.group == "config":
        import json as _json

        print(_json.dumps(_mcp_json_config(), ensure_ascii=False, indent=2))
        return 0
    if args.group == "setup":
        from jobfindsme.connectors.boss_zhipin import setup_chrome

        platforms = tuple(getattr(args, "platform", None) or ())
        result = setup_chrome(platforms)
        _emit(result, "markdown")
        return 0 if result["ok"] else 1
    if args.group in {"connect", "install", "upgrade", "uninstall"}:
        installer = HostInstaller(home=args.home)
        custom_path = getattr(args, "path", None)
        if custom_path:
            result = getattr(installer, args.group)("generic", config_path=custom_path)
        elif args.host:
            result = getattr(installer, args.group)(args.host)
        elif args.group == "connect":
            # Bare `jobfindsme connect`: detect the current agent automatically.
            host, candidates = detect_host(installer.home)
            if host is None and sys.stdin.isatty():
                host = _prompt_host(candidates)
            if host is None:
                _emit(
                    {
                        "ok": False,
                        "error": "未检测到当前 Agent，请显式指定",
                        "detected_candidates": candidates,
                        "hint": "jobfindsme connect <codex|claude|cursor>",
                    },
                    args.output,
                )
                return 1
            print(f"自动探测到当前 Agent: {host}", file=sys.stderr)
            result = installer.connect(host)
        else:
            raise ValueError("either host or --path is required")
    else:
        result = _execute(jobfindsmecore(args.db), args)
    _emit(
        result,
        args.output,
        job_list=args.group == "jobs" and args.action == "search",
    )
    return 0


def main() -> None:
    raise SystemExit(run())
