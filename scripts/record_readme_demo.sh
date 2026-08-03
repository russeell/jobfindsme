#!/bin/bash
set -euo pipefail

# Render README demo assets from REAL jobfindsme MCP output.
# The output is parsed into a designed chat-style page and captured with
# Chromium (Playwright) so text uses system fonts and stays crisp.
#
# Requirements: python3 with jobfindsme installed, playwright + chromium, Pillow.
#
# Outputs:
#   docs/demo-dark.gif / docs/demo-light.gif         - animated demo
#   docs/screenshot-dark.png / docs/screenshot-light.png - static 2x frame

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$ROOT/scripts/readme_demo"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 -c "import playwright" >/dev/null 2>&1 || {
  echo "missing playwright: pip install playwright && playwright install chromium" >&2
  exit 1
}

python3 "$DEMO_DIR/drive_mcp.py" --json-out "$WORK/output.json"

for theme in dark light; do
  python3 "$DEMO_DIR/render_demo.py" \
    "$WORK/output.json" "$WORK/demo-$theme.html" --theme "$theme"
  python3 "$DEMO_DIR/capture_demo.py" \
    "$WORK/demo-$theme.html" \
    "$ROOT/docs/demo-$theme.gif" \
    "$ROOT/docs/screenshot-$theme.png" \
    "$theme"
done

echo "Rendered docs/demo-{dark,light}.gif and docs/screenshot-{dark,light}.png"
