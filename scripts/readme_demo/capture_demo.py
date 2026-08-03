"""Capture the rendered demo page with Chromium into GIF + static PNG.

Usage: capture_demo.py <demo.html> <out.gif> <out.png> <dark|light>
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

VIEW_W, VIEW_H = 1280, 1300
FRAME_MS = 150
TOTAL_MS = 12600
BG = {"dark": (11, 15, 20), "light": (237, 241, 246)}


def fit_viewport(page) -> None:
    """Size the viewport to the demo window so captures contain no page bg."""
    page.wait_for_timeout(250)
    rect = page.evaluate(
        "() => { const r = document.querySelector('.win').getBoundingClientRect();"
        " return {w: Math.ceil(r.width), h: Math.ceil(r.height)}; }"
    )
    page.set_viewport_size({"width": rect["w"], "height": rect["h"]})
    page.wait_for_timeout(150)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_in", type=Path)
    parser.add_argument("gif_out", type=Path)
    parser.add_argument("png_out", type=Path)
    parser.add_argument("theme", choices=("dark", "light"))
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="jf-capture-") as tmp:
        frames: list[Path] = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": VIEW_W, "height": VIEW_H},
                device_scale_factor=1,
            )
            page.goto(args.html_in.as_uri())
            fit_viewport(page)
            for step in range(TOTAL_MS // FRAME_MS):
                page.wait_for_timeout(FRAME_MS)
                shot = Path(tmp) / f"frame-{step:03d}.png"
                page.locator(".win").screenshot(path=str(shot))
                frames.append(shot)

            static = browser.new_page(
                viewport={"width": VIEW_W, "height": VIEW_H},
                device_scale_factor=2,
            )
            static.add_init_script("window.__SKIP_TO_END__ = true;")
            static.goto(args.html_in.as_uri())
            fit_viewport(static)
            static.wait_for_timeout(600)
            static.locator(".win").screenshot(path=str(args.png_out))
            browser.close()

        images = [Image.open(f) for f in frames]
        width = max(img.width for img in images)
        height = max(img.height for img in images)
        padded = []
        for img in images:
            canvas = Image.new("RGB", (width, height), BG[args.theme])
            canvas.paste(img.convert("RGBA"), (0, 0), img.convert("RGBA"))
            padded.append(canvas)
        padded[0].save(
            args.gif_out,
            save_all=True,
            append_images=padded[1:],
            duration=FRAME_MS,
            loop=0,
            optimize=True,
        )
        print(f"saved {args.gif_out} ({len(padded)} frames) and {args.png_out}")


if __name__ == "__main__":
    main()
