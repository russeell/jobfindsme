#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d "${TMPDIR:-/tmp}/jobfindsme-wheel-smoke.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT

python -m pip wheel \
  "$root" \
  --no-deps \
  --no-build-isolation \
  --wheel-dir "$temporary/dist"

wheel="$(find "$temporary/dist" -name '*.whl' -print -quit)"
test -n "$wheel"

python -m venv --system-site-packages "$temporary/venv"
"$temporary/venv/bin/python" -m pip install --no-deps "$wheel"

database="$temporary/jobfindsme.db"
"$temporary/venv/bin/jobfindsme" \
  --db "$database" \
  workspace init \
  --name "Installed Package Smoke"
"$temporary/venv/bin/jobfindsme" --db "$database" doctor

(
cd "$temporary"
"$temporary/venv/bin/python" - "$database" <<'PY'
import json
import os
import sqlite3
import subprocess
import sys

database = sys.argv[1]
required = {
    "active_context",
    "candidate_profiles",
    "jobs",
    "search_plans",
    "source_subscriptions",
    "workspaces",
}
with sqlite3.connect(database) as connection:
    present = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
missing = required - present
if missing:
    raise SystemExit(f"installed wheel is missing tables: {sorted(missing)}")

request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "get_jobs", "arguments": {}},
}
completed = subprocess.run(
    [sys.executable, "-m", "jobfindsme.mcp"],
    input=json.dumps(request) + "\n",
    text=True,
    capture_output=True,
    check=True,
    env={**os.environ, "JOBFINDSME_DB_PATH": database},
)
response = json.loads(completed.stdout)
structured = response["result"]["structuredContent"]
if not isinstance(structured, dict) or structured.get("jobs") != []:
    raise SystemExit(f"invalid installed MCP empty result: {structured!r}")
PY
)
