#!/usr/bin/env python3
"""Generate jobfindsme README hero images — reproducible from real data.

Outputs:
  docs/search-results.png   — 1200x630 hero (brand panel + terminal demo)
  docs/demo.gif             — ~1100x700 loop: find → apply → schedule → history

Usage: python3 scripts/generate_hero.py
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

# ── Palette (GitHub dark + terminal green) ───────────────────────────────────
BG_TOP = (13, 17, 23)
BG_BOTTOM = (22, 27, 34)
PANEL = (26, 32, 42)
PANEL_BORDER = (48, 54, 61)
TITLEBAR = (33, 40, 50)
TEXT = (201, 209, 217)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
YELLOW = (210, 153, 34)
RED = (248, 81, 73)
BLUE = (88, 166, 255)
PURPLE = (197, 48, 208)
ACCENT = (88, 166, 255)

FONT_MONO = "/System/Library/Fonts/Menlo.ttc"
FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _rrect(draw: ImageDraw.ImageDraw, box, radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


# ── Terminal window ──────────────────────────────────────────────────────────


def terminal(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    lines: list[tuple[str, str]],  # (style, text); style: prompt/input/green/out
    *,
    font: ImageFont.FreeTypeFont,
    cjk: ImageFont.FreeTypeFont,
) -> None:
    """Draw a macOS-style terminal with traffic lights and styled lines."""
    _rrect(draw, (x, y, x + w, y + h), 14, PANEL)
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=14, outline=PANEL_BORDER, width=1
    )
    # Title bar
    draw.rounded_rectangle(
        (x + 1, y + 1, x + w - 1, y + 30), radius=13, fill=TITLEBAR
    )
    for i, color in enumerate((RED, YELLOW, GREEN)):
        draw.ellipse((x + 14 + i * 18, y + 11, x + 22 + i * 18, y + 19), fill=color)
    tw = draw.textlength(title, font=font)
    draw.text((x + w / 2 - tw / 2, y + 7), title, font=font, fill=DIM)
    # Body lines
    line_h = int(font.size * 1.55)
    cy = y + 42
    for style, text in lines:
        if style == "input":
            draw.text((x + 18, cy), "❯ ", font=font, fill=GREEN)
            draw.text((x + 18 + 34, cy), text, font=cjk, fill=TEXT)
        elif style == "prompt":
            draw.text((x + 18, cy), "user:", font=font, fill=BLUE)
            draw.text((x + 18 + 80, cy), text, font=cjk, fill=TEXT)
        elif style == "green":
            draw.text((x + 18, cy), text, font=cjk, fill=GREEN)
        elif style == "dim":
            draw.text((x + 18, cy), text, font=cjk, fill=DIM)
        elif style == "acc":
            draw.text((x + 18, cy), text, font=cjk, fill=ACCENT)
        else:  # out
            draw.text((x + 18, cy), text, font=cjk, fill=TEXT)
        cy += line_h


# ── Hero PNG ─────────────────────────────────────────────────────────────────


def render_hero(path: str) -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)
    # Vertical gradient
    for yy in range(H):
        t = yy / H
        draw.line(
            (0, yy, W, yy),
            fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM, strict=True)),
        )
    f_logo = _font(FONT_MONO, 30)
    f_big = _font(FONT_MONO, 40)
    f_cjk = _font(FONT_CJK, 22)
    f_small = _font(FONT_MONO, 16)
    f_small_cjk = _font(FONT_CJK, 15)

    # ── Left: brand panel ──
    lx = 46
    # logo mark
    _rrect(draw, (lx, 58, lx + 54, 112), 12, ACCENT)
    draw.text((lx + 15, 72), "J", font=f_big, fill=BG_TOP)
    draw.text((lx + 74, 64), "jobfindsme", font=f_logo, fill=TEXT)
    draw.text((lx + 74, 100), "AI 求职雷达 · MCP Server", font=f_small_cjk, fill=DIM)

    # three scenarios
    scenarios = [
        ("①", "找岗位", "一句话匹配岗位 + 投递链接"),
        ("②", "定时推送", "任意时间频率，投递过的不重推"),
        ("③", "查历史", "所有匹配过的岗位随时可查"),
    ]
    sy = 168
    for icon, name, desc in scenarios:
        _rrect(draw, (lx, sy, lx + 40, sy + 40), 10, (33, 40, 50))
        draw.text((lx + 11, sy + 6), icon, font=_font(FONT_CJK, 22), fill=ACCENT)
        draw.text((lx + 54, sy + 2), name, font=f_cjk, fill=TEXT)
        draw.text((lx + 54, sy + 26), desc, font=f_small_cjk, fill=DIM)
        sy += 58

    # tags
    ty = 352
    tags = ["BOSS直聘", "猎聘", "本地优先", "无 API Key"]
    tx = lx
    for tag in tags:
        tw = draw.textlength(tag, font=f_small_cjk) + 24
        _rrect(draw, (tx, ty, tx + tw, ty + 30), 15, (33, 40, 50))
        draw.text((tx + 12, ty + 6), tag, font=f_small_cjk, fill=DIM)
        tx += tw + 10

    # tagline
    draw.text(
        (lx, 430),
        "对 Agent 说一句话，剩下的交给它",
        font=f_cjk,
        fill=TEXT,
    )

    # ── Right: terminal ──
    lines = [
        ("prompt", "用 jobfindsme 根据简历找上海的 AI 应用工程师，20K以上"),
        ("dim", "→ 搜索 BOSS直聘·上海 · 猎聘·上海 … 完成 (4.2s)"),
        ("green", "🆕 新增 6 个匹配岗位（已过滤 42 → 20）"),
        ("out", "1. AI应用工程师（Agent开发）｜某知名公司｜上海｜40K-60K"),
        ("out", "2. AI应用工程师 ｜上汽云计算中心 ｜上海｜25K-40K"),
        ("out", "3. AI应用工程师（CAD方向）｜极芯拓方 ｜上海浦东｜40K-70K"),
        ("out", "4. AI应用工程师 ｜某上海基金公司 ｜上海｜20K-28K"),
        ("dim", "投递链接: https://www.liepin.com/job/1980438233.shtml"),
        ("green", "投递后说「标记第 2 个为已投递」— 明天自动跳过"),
    ]
    terminal(
        draw,
        430,
        58,
        724,
        520,
        "jobfindsme — zsh",
        lines,
        font=_font(FONT_MONO, 16),
        cjk=_font(FONT_CJK, 16),
    )
    img.save(path)
    print(f"✓ {path} ({W}x{H})")


# ── Demo GIF ────────────────────────────────────────────────────────────────


def render_gif(path: str) -> None:
    """Real-usage loop: type request → results → mark applied → schedule
    push → query history.  Terminal scrolls like a real session."""
    W, H = 1100, 700
    frames: list[Image.Image] = []
    delay_ms = 550
    MAX_LINES = 18  # visible terminal rows

    def new_frame() -> Image.Image:
        img = Image.new("RGB", (W, H), BG_TOP)
        draw = ImageDraw.Draw(img)
        for yy in range(H):
            t = yy / H
            draw.line(
                (0, yy, W, yy),
                fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM, strict=True)),
            )
        return img

    mono = _font(FONT_MONO, 17)
    cjk = _font(FONT_CJK, 17)

    # ── scrolling terminal history ──
    history: list[tuple[str, str]] = []

    def push(style: str, text: str) -> None:
        history.append((style, text))

    def snap() -> Image.Image:
        img = new_frame()
        draw = ImageDraw.Draw(img)
        terminal(
            draw, 60, 60, W - 120, H - 120, "jobfindsme — zsh",
            history[-MAX_LINES:], font=mono, cjk=cjk,
        )
        return img

    def typing(full: str, steps: int) -> None:
        """Typing animation: the last line grows char by char."""
        push("input", "")
        chunk = max(1, len(full) // steps)
        for i in range(1, steps + 1):
            history[-1] = ("input", full[: i * chunk])
            frames.append(snap())
        history[-1] = ("input", full)

    # ── Scene 1: find jobs ──
    typing("用 jobfindsme 根据简历找上海的 AI 应用工程师，20K以上", 5)
    push("dim", "→ BOSS直聘·上海 ✓ · 猎聘·上海 ✓ (4.2s)")
    frames.append(snap())
    push("green", "🆕 新增 6 个匹配岗位（已过滤 42 → 20）")
    frames.append(snap())
    for line in [
        ("out", "1. AI应用工程师（Agent开发）｜某知名公司｜上海｜40K-60K"),
        ("out", "2. AI应用工程师 ｜上汽云计算中心 ｜上海｜25K-40K"),
        ("out", "3. AI应用工程师（CAD方向）｜极芯拓方 ｜上海浦东｜40K-70K"),
        ("out", "4. AI应用工程师 ｜某上海基金公司 ｜上海｜20K-28K"),
    ]:
        push(*line)
        frames.append(snap())
    push("dim", "投递链接: https://www.liepin.com/job/1980438233.shtml")
    frames.append(snap())

    # ── Scene 2: mark applied ──
    typing("把第 2 个标记为已投递", 4)
    push("green", "✓ 已投递：AI应用工程师 ｜上汽云计算中心（明天推送自动跳过）")
    frames.append(snap())

    # ── Scene 3: schedule push ──
    typing("每天早上 9 点推送新岗位给我", 4)
    push("green", "✓ 已设置：每天 09:00 推送 · 只看新增 · 已投递不重推")
    frames.append(snap())
    push("acc", "📬 次日 09:00 → 推送新增 3 个匹配岗位")
    frames.append(snap())

    # ── Scene 4: query history ──
    typing("我投过哪些岗位？", 3)
    push("green", "📋 已投递 3 个岗位（最近优先）：")
    frames.append(snap())
    push("acc", "  · AI应用工程师 ｜上汽云计算中心 ｜07-31 已投递")
    frames.append(snap())
    push("acc", "  · AI应用工程师 ｜某上海基金公司 ｜07-30 已投递")
    frames.append(snap())

    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=delay_ms,
        loop=0,
        optimize=False,  # keep every frame so the scene loop is readable
        disposal=2,
    )
    import os

    print(f"✓ {path} ({W}x{H}, {len(frames)} 帧, {os.path.getsize(path)//1024} KB)")


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    docs = os.path.join(here, "..", "docs")
    render_hero(os.path.join(docs, "search-results.png"))
    render_gif(os.path.join(docs, "demo.gif"))
