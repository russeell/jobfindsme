#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d "${TMPDIR:-/tmp}/jobfindsme-wheel-smoke.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT
source_tree="$temporary/source"
mkdir -p "$source_tree"

(
  cd "$root"
  tar \
    --exclude='./.git' \
    --exclude='./build' \
    --exclude='./dist' \
    --exclude='./src/jobfindsme.egg-info' \
    -cf - .
) | tar -C "$source_tree" -xf -

build_options=()
if python -c "import setuptools.build_meta" >/dev/null 2>&1; then
  build_options+=(--no-build-isolation)
fi

python -m pip wheel \
  "$source_tree" \
  --no-deps \
  "${build_options[@]}" \
  --wheel-dir "$temporary/dist"

wheel="$(find "$temporary/dist" -name '*.whl' -print -quit)"
test -n "$wheel"

python - "$wheel" <<'PY'
import sys
import zipfile

wheel = sys.argv[1]
forbidden = (
    "jobfindsme/connectors/http_platforms.py",
    "jobfindsme/evaluation/",
    "jobfindsme/monitor_configs.py",
    "jobfindsme/monitoring/",
    "jobfindsme/notifications/",
)
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
leaked = [name for name in names if name.startswith(forbidden)]
if leaked:
    raise SystemExit(f"installed wheel contains retired modules: {leaked}")
required_resources = {
    "jobfindsme/resources/connectors/boss_fetch.js",
    "jobfindsme/resources/jobfindsme/SKILL.md",
    "jobfindsme/resources/taxonomy/skills.json",
}
missing_resources = required_resources - set(names)
if missing_resources:
    raise SystemExit(
        f"installed wheel is missing resources: {sorted(missing_resources)}"
    )
PY

python -m venv --system-site-packages "$temporary/venv"
"$temporary/venv/bin/python" -m pip install --no-deps "$wheel"

database="$temporary/jobfindsme.db"
"$temporary/venv/bin/jobfindsme" connect cursor --home "$temporary/home"
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

config = os.path.join(os.path.dirname(database), "home", ".cursor", "mcp.json")
if not os.path.exists(config):
    raise SystemExit("installed wheel could not configure Cursor")
PY
)
