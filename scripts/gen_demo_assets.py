#!/usr/bin/env python3
"""Render jobfindsme demo GIF + hero screenshot (terminal style, real output format)."""

from __future__ import annotations

from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Config ───────────────────────────────────────────────────────────────────
SCALE = 2  # render at 2x, downscale for outputs
BASE_W = 1200
FONT_SIZE = 26
LINE_H = 42
PAD_X = 44
PAD_TOP = 18
PAD_BOTTOM = 34
TITLEBAR_H = 64
EMOJI_SIZE = 30
EMOJI_ADV = 36

MENLO = "/System/Library/Fonts/Menlo.ttc"
HIRAGINO = "/System/Library/Fonts/Hiragino Sans GB.ttc"
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"

C = {
    "bg": (26, 27, 38),
    "titlebar": (38, 39, 52),
    "text": (202, 204, 216),
    "dim": (104, 110, 140),
    "prompt": (139, 173, 248),
    "green": (158, 206, 106),
    "gold": (224, 175, 104),
    "cyan": (125, 207, 255),
    "purple": (187, 154, 247),
    "orange": (255, 158, 100),
    "magenta": (247, 118, 142),
    "cursor": (147, 170, 240),
}

f_menlo = ImageFont.truetype(MENLO, FONT_SIZE * SCALE)
f_cjk = ImageFont.truetype(HIRAGINO, FONT_SIZE * SCALE)
f_title = ImageFont.truetype(MENLO, 22 * SCALE)
f_title_cjk = ImageFont.truetype(HIRAGINO, 22 * SCALE)
f_emoji = ImageFont.truetype(EMOJI_FONT, 160)

_MENLO_CMAP = TTCollection(MENLO).fonts[0].getBestCmap()

_emoji_cache: dict[str, Image.Image] = {}


def menlo_has(ch: str) -> bool:
    return ord(ch) in _MENLO_CMAP


def is_emoji(s: str, i: int) -> int:
    """Return cluster length (0 = not emoji)."""
    ch = s[i]
    if ch == "⚠" and i + 1 < len(s) and s[i + 1] == "\ufe0f":
        return 2
    cp = ord(ch)
    if 0x1F300 <= cp <= 0x1FAFF or cp == 0x2B50:
        return 1
    return 0


def emoji_tile(cluster: str) -> Image.Image:
    if cluster in _emoji_cache:
        return _emoji_cache[cluster]
    tile = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.text((20, 10), cluster, font=f_emoji, embedded_color=True)
    bbox = tile.getbbox()
    tile = tile.crop(bbox)
    # fit into square, keep aspect
    side = EMOJI_SIZE * SCALE
    ratio = min(side / tile.width, side / tile.height)
    tile = tile.resize(
        (max(1, int(tile.width * ratio)), max(1, int(tile.height * ratio))),
        Image.LANCZOS,
    )
    _emoji_cache[cluster] = tile
    return tile


def clusters(text: str):
    """Yield (kind, text): kind in {'emoji','menlo','cjk'}."""
    buf, buf_kind = "", None
    i = 0
    while i < len(text):
        n = is_emoji(text, i)
        if n:
            kind, piece = "emoji", text[i : i + n]
        else:
            piece = text[i]
            kind = "menlo" if menlo_has(piece) else "cjk"
        if buf_kind is None or kind == buf_kind and kind != "emoji":
            buf += piece
            buf_kind = kind
        else:
            if buf:
                yield buf_kind, buf
            buf, buf_kind = piece, kind
        i += n if n else 1
    if buf:
        yield buf_kind, buf


def draw_segment(
    img: Image.Image, d: ImageDraw.ImageDraw, x: int, y: int, text: str, color
):
    for kind, piece in clusters(text):
        if kind == "emoji":
            tile = emoji_tile(piece)
            ty = y + (LINE_H * SCALE - tile.height) // 2 - 2 * SCALE
            img.alpha_composite(tile, (int(x), int(ty)))
            x += EMOJI_ADV * SCALE
        else:
            font = f_menlo if kind == "menlo" else f_cjk
            d.text((x, y), piece, font=font, fill=color)
            x += d.textlength(piece, font=font)
    return x


def segment_width(d: ImageDraw.ImageDraw, text: str) -> float:
    w = 0.0
    for kind, piece in clusters(text):
        if kind == "emoji":
            w += EMOJI_ADV * SCALE
        else:
            w += d.textlength(piece, font=f_menlo if kind == "menlo" else f_cjk)
    return w


# ── Scene definition ─────────────────────────────────────────────────────────
PROMPT_1 = "用 jobfindsme，根据 ~/Documents/resume.pdf，"
PROMPT_2 = "找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。"


def prompt_lines(typed: int):
    """Prompt with typing progress. typed = number of chars revealed."""
    total_1 = len(PROMPT_1)
    p1 = PROMPT_1[: min(typed, total_1)]
    p2 = PROMPT_2[: max(0, typed - total_1)]
    lines = [[("❯ ", "green"), (p1, "prompt")]]
    if typed > total_1:
        lines.append([("  ", "green"), (p2, "prompt")])
    return lines


SEARCH_HEAD = [("● ", "purple"), ("搜索 5 个招聘平台…", "text")]
PLATFORMS = [
    [
        ("  ✓ ", "green"),
        ("BOSS直聘", "text"),
        (" ·········· ", "dim"),
        ("15 条", "green"),
    ],
    [
        ("  ✓ ", "green"),
        ("猎聘", "text"),
        (" ·············· ", "dim"),
        ("42 条", "green"),
    ],
    [
        ("  ✓ ", "green"),
        ("前程无忧", "text"),
        (" ·········· ", "dim"),
        ("20 条", "green"),
    ],
    [
        ("  ✓ ", "green"),
        ("智联招聘", "text"),
        (" ·········· ", "dim"),
        ("15 条", "green"),
    ],
    [
        ("  ✓ ", "green"),
        ("拉勾", "text"),
        (" ·············· ", "dim"),
        ("15 条", "green"),
    ],
]
RESUME = [
    ("● ", "purple"),
    ("简历解析完成：", "text"),
    ("技能 12 项 · 经验约 5 年 · 本科", "cyan"),
]
FILTER = [
    ("● ", "purple"),
    ("107 条 → 去重 → 硬过滤 → 匹配 ≥10% → ", "text"),
    ("Top 15", "gold"),
]

BLOCK_1 = [
    [
        ("🥇 ", ""),
        ("AI应用工程师｜示例科技｜上海·浦东｜社招｜正式｜", "text"),
        ("🎯 ", ""),
        ("86%", "magenta"),
    ],
    [("   💰 ", ""), ("25-40K·14薪", "green")],
    [("   🔗 ", ""), ("https://www.zhipin.com/job_detail/a1b2c3d4.html", "cyan")],
    [
        ("   💡 ", ""),
        ("职位名称直接匹配目标岗位；简历技能覆盖：Python, RAG, Agent", "dim"),
    ],
    [("   ⚠️ ", ""), ("必备技能缺口：Kubernetes", "orange")],
]
BLOCK_2 = [
    [
        ("🥈 ", ""),
        ("大模型应用工程师｜示例智能｜杭州｜社招｜正式｜", "text"),
        ("🎯 ", ""),
        ("81%", "magenta"),
    ],
    [("   💰 ", ""), ("20-35K", "green")],
    [("   🔗 ", ""), ("https://www.liepin.com/job/e5f6g7h8.html", "cyan")],
    [
        ("   💡 ", ""),
        ("匹配关键词：大模型, 应用, 工程师；简历技能覆盖：Python, LLM", "dim"),
    ],
]
BLOCK_3 = [
    [
        ("🥉 ", ""),
        ("AI Agent 工程师｜示例信息｜上海｜社招｜正式｜", "text"),
        ("🎯 ", ""),
        ("76%", "magenta"),
    ],
    [("   💰 ", ""), ("22-38K·13薪", "green")],
    [("   🔗 ", ""), ("https://we.51job.com/pc/job/i9j0k1l2.html", "cyan")],
    [("   💡 ", ""), ("简历技能覆盖：Agent, LangChain, Python", "dim")],
]
ELLIPSIS = [("  ··· 其余 13 条结果已省略（匹配度 74% – 41%）", "dim")]


def build_rest(include_block3: bool):
    rest = [SEARCH_HEAD, *PLATFORMS, RESUME, FILTER, [], *BLOCK_1, [], *BLOCK_2]
    if include_block3:
        rest += [[], *BLOCK_3]
    else:
        rest += [ELLIPSIS]
    return rest


# ── Frame rendering ──────────────────────────────────────────────────────────
def render_frame(lines, cursor_at=None, title="jobfindsme demo", total_lines=None):
    """lines: list of segment-lists. cursor_at: (line_idx, x_offset_px) or None."""
    n = total_lines if total_lines is not None else len(lines)
    h = TITLEBAR_H * SCALE + PAD_TOP * SCALE + n * LINE_H * SCALE + PAD_BOTTOM * SCALE
    img = Image.new("RGBA", (BASE_W * SCALE, h), C["bg"] + (255,))
    d = ImageDraw.Draw(img)
    # titlebar
    d.rectangle([0, 0, img.width, TITLEBAR_H * SCALE], fill=C["titlebar"])
    for i, col in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        cx = (44 + i * 40) * SCALE
        cy = TITLEBAR_H * SCALE // 2
        r = 11 * SCALE
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    title_w = sum(
        d.textlength(p, font=f_title if menlo_has(p) else f_title_cjk) for p in title
    )
    tx = (img.width - title_w) / 2
    ty = (TITLEBAR_H * SCALE - 30 * SCALE) / 2
    for p in title:
        font = f_title if menlo_has(p) else f_title_cjk
        d.text((tx, ty), p, font=font, fill=C["dim"])
        tx += d.textlength(p, font=font)
    # content
    y = TITLEBAR_H * SCALE + PAD_TOP * SCALE
    for li, segments in enumerate(lines):
        x = PAD_X * SCALE
        for text, color_key in segments:
            if not text:
                continue
            x = draw_segment(img, d, x, y, text, C.get(color_key, C["text"]))
        if cursor_at and cursor_at[0] == li:
            cx = PAD_X * SCALE + cursor_at[1]
            d.rectangle(
                [cx, y + 5 * SCALE, cx + 13 * SCALE, y + 35 * SCALE], fill=C["cursor"]
            )
        y += LINE_H * SCALE
    return img


def cursor_x_for(d_img, segments) -> int:
    probe = Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(probe)
    return int(sum(segment_width(d, text) for text, _ in segments if text))


def rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=255)
    out = img.copy()
    out.putalpha(mask)
    return out


# ── 1) demo.gif ──────────────────────────────────────────────────────────────
def gen_gif(path: str, width_out: int = 1100):
    rest = build_rest(include_block3=False)
    full_prompt = prompt_lines(len(PROMPT_1) + len(PROMPT_2))
    all_lines = [*full_prompt, [], *rest]
    total = len(all_lines)
    frames: list[Image.Image] = []
    durations: list[int] = []

    rf = lambda lines, cursor_at=None: render_frame(  # noqa: E731
        lines, cursor_at=cursor_at, total_lines=total
    )

    typed_total = len(PROMPT_1) + len(PROMPT_2)
    # empty start
    frames.append(rf(prompt_lines(0), cursor_at=(0, 0)))
    durations.append(500)
    # typing
    step = 3
    for t in range(step, typed_total + step, step):
        t = min(t, typed_total)
        lines = prompt_lines(t)
        cur_line = len(lines) - 1
        cx = cursor_x_for(None, lines[cur_line])
        frames.append(rf(lines, cursor_at=(cur_line, cx)))
        durations.append(60)
        if t >= typed_total:
            break
    # pause after prompt
    frames.append(rf(all_lines[: len(full_prompt)]))
    durations.append(550)
    # reveal rest line by line
    for k in range(1, len(rest) + 1):
        shown = [*full_prompt, [], *rest[:k]]
        frames.append(rf(shown))
        line = rest[k - 1]
        if line is SEARCH_HEAD:
            durations.append(600)
        elif line in PLATFORMS:
            durations.append(240)
        elif line in (RESUME, FILTER):
            durations.append(380)
        elif line == []:
            durations.append(200)
        else:
            durations.append(140)
    # final blink + hold
    last_idx = len(all_lines) - 1
    cx = cursor_x_for(None, all_lines[last_idx]) + 8
    frames.append(rf(all_lines, cursor_at=(last_idx, cx)))
    durations.append(800)
    frames.append(rf(all_lines))
    durations.append(400)
    frames.append(rf(all_lines, cursor_at=(last_idx, cx)))
    durations.append(1800)

    # downscale + shared palette
    ratio = width_out / frames[0].width
    size = (width_out, int(frames[0].height * ratio))
    small = [f.convert("RGB").resize(size, Image.LANCZOS) for f in frames]
    palette_src = small[-1].convert("P", palette=Image.ADAPTIVE, colors=256)
    paletted = [f.quantize(palette=palette_src, dither=Image.NONE) for f in small]
    paletted[0].save(
        path,
        save_all=True,
        append_images=paletted[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"GIF: {path}  frames={len(frames)}  size={size}")


# ── 2) search-results.png ────────────────────────────────────────────────────
def gen_png(path: str, width_out: int = 1600):
    rest = build_rest(include_block3=True)
    full_prompt = prompt_lines(len(PROMPT_1) + len(PROMPT_2))
    all_lines = [*full_prompt, [], *rest]
    last_idx = len(all_lines) - 1
    cx = cursor_x_for(None, all_lines[last_idx]) + 8
    win = render_frame(
        all_lines, cursor_at=(last_idx, cx), title="jobfindsme — 求职搜索"
    )
    win = rounded(win, 20 * SCALE)

    margin, shadow_off = 90 * SCALE, 26 * SCALE
    canvas = Image.new(
        "RGBA", (win.width + margin * 2, win.height + margin * 2), (0, 0, 0, 0)
    )
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [
            margin,
            margin + shadow_off,
            margin + win.width,
            margin + shadow_off + win.height,
        ],
        radius=20 * SCALE,
        fill=(10, 10, 25, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(28 * SCALE))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(win, (margin, margin))

    ratio = width_out / canvas.width
    canvas = canvas.resize((width_out, int(canvas.height * ratio)), Image.LANCZOS)
    canvas.save(path, optimize=True)
    print(f"PNG: {path}  size={canvas.size}")


if __name__ == "__main__":
    import sys

    gen_gif(sys.argv[1])
    gen_png(sys.argv[2])
