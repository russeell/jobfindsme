#!/bin/bash
set -euo pipefail

# Render README demo assets from the latest sanitized real-world report.
# The output is parsed into a designed chat-style page and captured with
# Chromium (Playwright) so text uses system fonts and stays crisp.
#
# Requirements: python3 with jobfindsme installed, playwright + chromium, Pillow.
#
# Output: docs/readme-demo.png (black theme, static 2x frame)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$ROOT/scripts/readme_demo"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -c "import playwright" >/dev/null 2>&1 || {
  echo "missing playwright: pip install playwright && playwright install chromium" >&2
  exit 1
}

REPORT="$ROOT/reports/real-world/latest_four_source_search.json"
if [[ ! -f "$REPORT" ]]; then
  echo "missing real-world report: run scripts/real_world_smoke.py first" >&2
  exit 1
fi

python3 "$DEMO_DIR/drive_mcp.py" \
  --report "$REPORT" \
  --json-out "$WORK/output.json"

python3 "$DEMO_DIR/render_demo.py" \
  "$WORK/output.json" "$WORK/demo-dark.html" --theme dark
python3 "$DEMO_DIR/capture_demo.py" \
  "$WORK/demo-dark.html" \
  "$WORK/demo-dark.gif" \
  "$ROOT/docs/readme-demo.png" \
  dark

echo "Rendered docs/readme-demo.png"
