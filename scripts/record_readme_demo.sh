#!/bin/bash
set -euo pipefail

# Record real jobfindsme MCP output and render README demo assets.
# Requirements: asciinema, agg (asciinema gif generator), Pillow.
#
# Outputs:
#   docs/demo-dark.gif / docs/demo-light.gif       - animated terminal demo
#   docs/screenshot-dark.png / docs/screenshot-light.png - static final frame

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO_DIR="$ROOT/scripts/readme_demo"
CAST_DIR="$(mktemp -d)"
trap 'rm -rf "$CAST_DIR"' EXIT

for tool in asciinema agg; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "missing required tool: $tool (brew install $tool)" >&2
    exit 1
  fi
done

FONT="JetBrains Mono,PingFang SC"

# Animated GIFs (24 rows; content scrolls like a real terminal).
ROWS=24 COLS=104 asciinema rec "$CAST_DIR/demo.cast" --overwrite \
  -c "ROWS=24 COLS=104 $DEMO_DIR/record_demo.sh" -q
agg --font-size 15 --line-height 1.3 --theme dracula \
  --text-font-family "$FONT" --idle-time-limit 0.25 --fps-cap 12 \
  --speed 1.5 --cols 104 --rows 24 \
  "$CAST_DIR/demo.cast" "$ROOT/docs/demo-dark.gif" -q
agg --font-size 15 --line-height 1.3 --theme github-light \
  --text-font-family "$FONT" --idle-time-limit 0.25 --fps-cap 12 \
  --speed 1.5 --cols 104 --rows 24 \
  "$CAST_DIR/demo.cast" "$ROOT/docs/demo-light.gif" -q

# Static screenshots (74 rows so the whole five-section output is visible).
ROWS=74 COLS=120 asciinema rec "$CAST_DIR/static.cast" --overwrite \
  -c "ROWS=74 COLS=120 $DEMO_DIR/record_demo.sh" -q
agg --font-size 14 --line-height 1.25 --theme dracula \
  --text-font-family "$FONT" --idle-time-limit 0.25 --fps-cap 12 \
  --speed 1.5 --cols 120 --rows 74 \
  "$CAST_DIR/static.cast" "$CAST_DIR/static-dark.gif" -q
agg --font-size 14 --line-height 1.25 --theme github-light \
  --text-font-family "$FONT" --idle-time-limit 0.25 --fps-cap 12 \
  --speed 1.5 --cols 120 --rows 74 \
  "$CAST_DIR/static.cast" "$CAST_DIR/static-light.gif" -q

python3 "$DEMO_DIR/gif_last_frame.py" "$CAST_DIR/static-dark.gif" "$ROOT/docs/screenshot-dark.png"
python3 "$DEMO_DIR/gif_last_frame.py" "$CAST_DIR/static-light.gif" "$ROOT/docs/screenshot-light.png"

echo "Rendered docs/demo-{dark,light}.gif and docs/screenshot-{dark,light}.png"
