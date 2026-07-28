from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from jobfindsme.core import JobFindsMeCore


def default_database_path() -> Path:
    override = os.getenv("JOBFINDSME_DB_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".jobfindsme" / "data" / "jobfindsme.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobfindsme")
    parser.add_argument("--db", type=Path, default=default_database_path())
    groups = parser.add_subparsers(dest="group", required=True)

    workspace = groups.add_parser("workspace")
    workspace_actions = workspace.add_subparsers(dest="action", required=True)
    workspace_init = workspace_actions.add_parser("init")
    workspace_init.add_argument("--name", default="My Job Search")
    workspace_actions.add_parser("list")

    plan = groups.add_parser("plan")
    plan_actions = plan.add_subparsers(dest="action", required=True)
    plan_add = plan_actions.add_parser("add")
    plan_add.add_argument("--workspace", required=True)
    plan_add.add_argument("--name", required=True)
    plan_add.add_argument("--role", action="append", required=True)
    plan_add.add_argument("--city", action="append", default=[])
    plan_add.add_argument("--salary-min-k", type=int)
    plan_add.add_argument("--salary-max-k", type=int)
    plan_add.add_argument("--experience-min-years", type=int)
    plan_add.add_argument("--experience-max-years", type=int)
    plan_add.add_argument("--exclude", action="append", default=[])

    plan_list = plan_actions.add_parser("list")
    plan_list.add_argument("--workspace", required=True)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    core = JobFindsMeCore(args.db)

    if args.group == "workspace" and args.action == "init":
        print(core.create_workspace(args.name).model_dump_json())
        return 0
    if args.group == "workspace" and args.action == "list":
        print(
            json.dumps(
                [item.model_dump(mode="json") for item in core.list_workspaces()],
                ensure_ascii=False,
            )
        )
        return 0
    if args.group == "plan" and args.action == "add":
        plan = core.create_search_plan(
            workspace_id=args.workspace,
            name=args.name,
            target_roles=args.role,
            locations=args.city,
            salary_min_k=args.salary_min_k,
            salary_max_k=args.salary_max_k,
            experience_min_years=args.experience_min_years,
            experience_max_years=args.experience_max_years,
            exclusions=args.exclude,
        )
        print(plan.model_dump_json())
        return 0
    if args.group == "plan" and args.action == "list":
        print(
            json.dumps(
                [
                    item.model_dump(mode="json")
                    for item in core.list_search_plans(args.workspace)
                ],
                ensure_ascii=False,
            )
        )
        return 0
    raise AssertionError("argparse accepted an unsupported command")


def main() -> None:
    raise SystemExit(run())
