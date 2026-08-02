"""Drive the real jobfindsme MCP server and print the five-section result.

The demo uses a throwaway SQLite database in a temp dir and generic fixture
resume/jobs — no personal folders, workspace IDs, or real job IDs appear.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESUME = HERE / "resume.md"
JOBS = HERE / "jobs.json"


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="jobfindsme-readme-demo-")
    db = Path(tmp) / "demo.db"
    env = dict(os.environ)
    env["JOBFINDSME_DB_PATH"] = str(db)
    proc = subprocess.Popen(
        [sys.executable, "-m", "jobfindsme.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        text=True,
    )

    def call(obj: dict) -> dict:
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    def notify(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    call(
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "readme-demo", "version": "1.0"},
            },
        }
    )
    notify({"jsonrpc": "2.0", "method": "notifications/initialized"})

    imported = call(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "setup_profile",
                "arguments": {"action": "import", "resume_path": str(RESUME)},
            },
        }
    )
    assert not imported.get("isError"), imported

    from jobfindsme.core import jobfindsmecore
    from jobfindsme.importing.parsers import parse_json

    core = jobfindsmecore(db)
    ws = core.list_workspaces()[0]
    with open(JOBS, encoding="utf-8") as fh:
        rows = json.load(fh)

    def source_for(row: dict) -> str:
        if "zhipin" in row["url"]:
            return "BOSS直聘·" + ("上海" if row["location"] == "上海" else "杭州")
        return "猎聘·" + ("上海" if row["location"] == "上海" else "杭州")

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(source_for(row), []).append(row)
    for source_name, group_rows in grouped.items():
        records = parse_json(
            json.dumps(group_rows, ensure_ascii=False),
            source_name=source_name,
        )
        core.job_imports.import_records(ws.workspace_id, records)

    configured = call(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "configure_search",
                "arguments": {
                    "target_roles": ["AI应用工程师", "Agent工程师"],
                    "locations": ["上海", "杭州"],
                    "salary_min_k": 20,
                    "recruitment_track": "social",
                    "employment_type": "full_time",
                    "exclusions": ["外包", "驻场"],
                },
            },
        }
    )
    assert not configured.get("isError"), configured

    searched = call(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_jobs",
                "arguments": {
                    "refresh_mode": "cache",
                    "include_seen": True,
                    "use_profile": True,
                    "limit": 5,
                },
            },
        }
    )
    if searched.get("isError") or "error" in searched:
        raise SystemExit(
            "search_jobs failed: " + json.dumps(searched, ensure_ascii=False)[:2000]
        )
    text = searched["result"]["content"][0]["text"]

    # Stream the five sections the way an Agent streams its answer.
    sections = text.split("\n\n")
    for index, section in enumerate(sections):
        for line in section.splitlines():
            print(line, flush=True)
            time.sleep(0.12 if line.startswith("【") else 0.04)
        if index < len(sections) - 1:
            print(flush=True)
            time.sleep(0.35)
    proc.terminate()


if __name__ == "__main__":
    main()
