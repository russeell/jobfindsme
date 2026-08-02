"""Extract the last frame of a GIF as a PNG (used for README screenshots)."""

from __future__ import annotations

import sys

from PIL import Image


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    gif = Image.open(src)
    gif.seek(gif.n_frames - 1)
    gif.save(dst)
    print(f"saved {dst} ({gif.size[0]}x{gif.size[1]})")


if __name__ == "__main__":
    main()
