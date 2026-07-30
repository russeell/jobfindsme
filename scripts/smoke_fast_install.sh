#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d "${TMPDIR:-/tmp}/jobfindsme-fast-install.XXXXXX")"
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

max_seconds="${JOBFINDSME_INSTALL_MAX_SECONDS:-180}"
started_at="$(date +%s)"

python -m venv "$temporary/venv"
"$temporary/venv/bin/python" -m pip install --upgrade pip build
"$temporary/venv/bin/python" -m build \
  --wheel "$source_tree" --outdir "$temporary/dist"

wheel="$(find "$temporary/dist" -name '*.whl' -print -quit)"
test -n "$wheel"
"$temporary/venv/bin/python" -m pip install "${wheel}[browser]"
"$temporary/venv/bin/python" - <<'PY'
from importlib.util import find_spec

if find_spec("playwright") is not None:
    raise SystemExit("fast install unexpectedly included Playwright")
PY
"$temporary/venv/bin/python" -m jobfindsme connect workbuddy \
  --home "$temporary/home"
"$temporary/venv/bin/python" -m jobfindsme --version

config="$temporary/home/.workbuddy/mcp.json"
test -f "$config"

elapsed="$(( $(date +%s) - started_at ))"
printf 'clean install + WorkBuddy setup: %ss (limit: %ss)\n' \
  "$elapsed" "$max_seconds"
test "$elapsed" -le "$max_seconds"
