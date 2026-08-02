"""Render README demo assets from the fixed jobfindsme output contract.

Produces four deterministic assets:
  docs/demo-dark.gif        - animated chat demo (GitHub dark theme)
  docs/demo-light.gif       - animated chat demo (GitHub light theme)
  docs/screenshot-dark.png  - final frame, transparent rounded window
  docs/screenshot-light.png - final frame, transparent rounded window

The README switches theme via <picture prefers-color-scheme>.  Content is a
reproducible sample of the exact five-section shape the MCP server returns.
"""

# ruff: noqa: E501  # long UI strings are intentional here

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

FONT_CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_MONO = "/System/Library/Fonts/Menlo.ttc"

WIDTH, HEIGHT = 1320, 940
MARGIN = 44
HEADER_H = 74
FOOTER_H = 48

PROMPT = (
    "用 jobfindsme，根据 ~/Documents/resume.pdf 找上海/杭州 AI 应用工程师，20K+，社招。"
)


@dataclass(frozen=True)
class Theme:
    name: str
    page: str
    window: str
    border: str
    header: str
    text: str
    muted: str
    blue: str
    green: str
    yellow: str
    prompt_bg: str
    card: str
    chip_bg: str
    badge_bg: str
    rule: str


DARK = Theme(
    name="dark",
    page="#0b0f14",
    window="#0f172a",
    border="#263244",
    header="#111c31",
    text="#e5edf7",
    muted="#8ea0b4",
    blue="#60a5fa",
    green="#7dd3a7",
    yellow="#f2c76b",
    prompt_bg="#1e3a8a",
    card="#14213a",
    chip_bg="#1b3352",
    badge_bg="#12305e",
    rule="#1e293b",
)

LIGHT = Theme(
    name="light",
    page="#f1f5f9",
    window="#ffffff",
    border="#dbe3ec",
    header="#f8fafc",
    text="#0f172a",
    muted="#64748b",
    blue="#2563eb",
    green="#0f9f6e",
    yellow="#b45309",
    prompt_bg="#2563eb",
    card="#f8fafc",
    chip_bg="#eef4ff",
    badge_bg="#dbeafe",
    rule="#e8eef5",
)


def _font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_MONO if mono else FONT_CJK, size=size)


F_TITLE = _font(28)
F_BODY = _font(22)
F_META = _font(20)
F_SMALL = _font(17)
F_BADGE = _font(16)
F_MONO = _font(18, mono=True)


def _tw(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(text, font=font))


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    width: int,
) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if _tw(draw, candidate, font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def _rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _window(
    img: Image.Image, theme: Theme
) -> tuple[ImageDraw.ImageDraw, int, int, int, int]:
    draw = ImageDraw.Draw(img)
    x0, y0 = MARGIN, MARGIN
    x1, y1 = WIDTH - MARGIN, HEIGHT - MARGIN
    for offset, alpha in ((12, 22), (7, 36), (3, 48)):
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (x0 + 4, y0 + offset, x1 + 4, y1 + offset),
            radius=30,
            fill=(0, 0, 0, alpha),
        )
        img.alpha_composite(shadow)
    _rounded(
        draw,
        (x0, y0, x1, y1),
        radius=30,
        fill=theme.window,
        outline=theme.border,
        width=1,
    )
    _rounded(draw, (x0, y0, x1, y0 + HEADER_H), radius=30, fill=theme.header)
    draw.rounded_rectangle(
        (x0, y0 + HEADER_H - 22, x1, y0 + HEADER_H - 20), radius=0, fill=theme.rule
    )
    for i, color in enumerate(("#f87171", "#fbbf24", "#34d399")):
        cx = x0 + 34 + i * 30
        draw.ellipse((cx - 7, y0 + 27, cx + 7, y0 + 41), fill=color)
    draw.text(
        (x0 + 130, y0 + 22), "jobfindsme · AI 求职雷达", fill=theme.text, font=F_BADGE
    )
    badge = "本地优先 · MCP Server"
    bw = _tw(draw, badge, F_BADGE)
    bx = x1 - 34 - bw - 30
    _rounded(draw, (bx, y0 + 20, bx + bw + 30, y0 + 56), radius=16, fill=theme.badge_bg)
    draw.text((bx + 15, y0 + 25), badge, fill=theme.blue, font=F_BADGE)
    return draw, x0, y0, x1, y1


def _footer(draw: ImageDraw.ImageDraw, theme: Theme, x0: int, y1: int) -> None:
    draw.rounded_rectangle(
        (x0 + 36, y1 - FOOTER_H - 14, WIDTH - x0 - 36, y1 - 18),
        radius=16,
        fill=theme.card,
    )
    text = "本地优先 · 简历不出本机 · SQLite 持久化 · 无需模型 API"
    tw = _tw(draw, text, F_SMALL)
    draw.text(
        ((WIDTH - tw) // 2, y1 - FOOTER_H - 8), text, fill=theme.muted, font=F_SMALL
    )


def _prompt(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    x: int,
    y: int,
    max_w: int,
    text: str,
) -> int:
    lines = _wrap(draw, text, F_BODY, max_w - 110)
    block_h = 20 + len(lines) * (F_BODY.size + 6) + 18
    _rounded(draw, (x, y, x + max_w, y + block_h), radius=22, fill=theme.prompt_bg)
    draw.text((x + 22, y + 14), "你", fill="#ffffff", font=F_META)
    ty = y + 14
    for line in lines:
        draw.text((x + 70, ty), line, fill="#ffffff", font=F_BODY)
        ty += F_BODY.size + 6
    return block_h


def _text(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    x: int,
    y: int,
    text: str,
    *,
    font: ImageFont.FreeTypeFont,
    color: str,
    max_w: int,
) -> int:
    for line in _wrap(draw, text, font, max_w):
        draw.text((x, y), line, fill=color, font=font)
        y += font.size + 6
    return len(_wrap(draw, text, font, max_w)) * (font.size + 6) - 6


def _chip(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    x: int,
    y: int,
    text: str,
    color: str,
) -> int:
    w = _tw(draw, text, F_META)
    _rounded(
        draw,
        (x - 12, y - 7, x + w + 14, y + F_META.size + 9),
        radius=14,
        fill=theme.chip_bg,
    )
    draw.text((x, y), text, fill=color, font=F_META)
    return F_META.size + 16


def _job_card(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    x: int,
    y: int,
    max_w: int,
    *,
    title: str,
    meta: str,
    score: str,
    link: str,
    reason: str,
    warning: str | None = None,
) -> int:
    inner = x + 24
    card_h = (
        24
        + F_META.size
        + 10
        + F_META.size
        + 10
        + F_MONO.size
        + 8
        + 2 * (F_META.size + 6)
        + 12
    )
    if warning:
        card_h += F_META.size + 10
    _rounded(
        draw,
        (x - 8, y, x + max_w + 8, y + card_h),
        radius=18,
        fill=theme.card,
        outline=theme.rule,
        width=1,
    )

    draw.text((inner, y + 12), title, fill=theme.text, font=F_META)
    sw = _tw(draw, score, F_META)
    _rounded(
        draw,
        (x + max_w - 8 - sw - 26, y + 12, x + max_w - 8, y + F_META.size + 30),
        radius=13,
        fill=theme.badge_bg,
    )
    draw.text((x + max_w - 8 - sw - 13, y + 17), score, fill=theme.blue, font=F_META)

    ty = y + 12 + F_META.size + 10
    draw.text((inner, ty), meta, fill=theme.muted, font=F_META)
    ty += F_META.size + 10
    draw.text((inner, ty), "投递链接：", fill=theme.blue, font=F_META)
    draw.text(
        (inner + _tw(draw, "投递链接：", F_META), ty),
        link,
        fill=theme.blue,
        font=F_MONO,
    )
    ty += F_MONO.size + 8
    draw.text((inner, ty), "推荐理由：" + reason, fill=theme.text, font=F_META)
    ty += F_META.size + 8
    if warning:
        draw.text((inner, ty), "需要注意：" + warning, fill=theme.yellow, font=F_META)
    return card_h + 10


def _compact_row(
    draw: ImageDraw.ImageDraw,
    theme: Theme,
    x: int,
    y: int,
    max_w: int,
    *,
    title: str,
    score: str,
) -> int:
    h = F_META.size + 34
    _rounded(
        draw,
        (x - 8, y, x + max_w + 8, y + h),
        radius=16,
        fill=theme.card,
        outline=theme.rule,
        width=1,
    )
    draw.text((x + 20, y + 12), title, fill=theme.text, font=F_META)
    sw = _tw(draw, score, F_META)
    _rounded(
        draw,
        (x + max_w - 8 - sw - 26, y + 10, x + max_w - 8, y + F_META.size + 26),
        radius=12,
        fill=theme.badge_bg,
    )
    draw.text((x + max_w - 8 - sw - 13, y + 14), score, fill=theme.blue, font=F_META)
    return h + 12


def render(
    visible: list[tuple[str, str]],
    theme: Theme,
    *,
    prompt: str,
    status: str | None,
) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw, x0, y0, x1, y1 = _window(img, theme)
    cx = x0 + 40
    max_w = x1 - x0 - 80
    y = y0 + HEADER_H + 30

    y += _prompt(draw, theme, cx, y, max_w, prompt) + 8
    if status:
        y += (
            _text(
                draw, theme, cx, y, status, font=F_META, color=theme.green, max_w=max_w
            )
            + 4
        )

    for kind, text in visible:
        if not text:
            y += 4
            continue
        if kind == "card":
            y += _job_card(draw, theme, cx, y, max_w, **_CARDS[text])
        elif kind == "compact":
            y += _compact_row(draw, theme, cx, y, max_w, **_COMPACT_CARDS[text])
        elif kind == "section":
            y += _chip(draw, theme, cx, y, text, theme.green)
        elif kind == "body":
            y += (
                _text(
                    draw, theme, cx, y, text, font=F_META, color=theme.text, max_w=max_w
                )
                + 2
            )
        elif kind == "muted":
            y += (
                _text(
                    draw,
                    theme,
                    cx,
                    y,
                    text,
                    font=F_META,
                    color=theme.muted,
                    max_w=max_w,
                )
                + 2
            )
        if y > y1 - FOOTER_H - 34:
            break
    _footer(draw, theme, x0, y1)
    return img


_CARDS = {
    "job1": dict(
        title="1. [新增] AI Agent应用工程师｜星河科技｜上海｜社招｜正式｜25-40K",
        meta="技能：RAG、Agent、MCP ｜ 经验：1-3年 ｜ 学历：本科",
        score="匹配度 92%",
        link="https://www.zhipin.com/job_detail/example-ai-agent.html",
        reason="简历技能命中：RAG、Agent、MCP；综合匹配度 92%；薪资信息明确。",
    ),
}

_COMPACT_CARDS = {
    "job2": dict(
        title="2. [新增] 大模型应用开发工程师｜云帆智能｜杭州｜22-35K",
        score="匹配度 87%",
    ),
}


def _visible_groups() -> list[list[tuple[str, str]]]:
    return [
        [
            ("section", "【1·简历解析】"),
            ("body", "简历解析：技能 17 项 ｜ 项目 2 项 ｜ 经验 3 项 ｜ 学历：硕士"),
        ],
        [
            ("section", "【2·检索概览】"),
            ("muted", "猎聘 √(60) · BOSS直聘 √(42) · 共发现 102 条"),
        ],
        [
            ("section", "【3·过滤说明】"),
            ("body", "过滤：角色 + 上海/杭州 + 20K+ + 社招 + 正式 → 8 个"),
        ],
        [("section", "【4·岗位列表】"), ("card", "job1")],
        [("compact", "job2")],
        [
            ("section", "【5·说明】"),
            ("body", "结果：历史 96 · 本次 8（全部新增）· 累计 152 · 关闭 12"),
        ],
    ]


def scenes_for(theme: Theme) -> list[tuple[Image.Image, int]]:
    """(frame, duration_ms) sequence: typing -> search -> progressive reveal."""
    frames: list[tuple[Image.Image, int]] = []
    for i in range(len(PROMPT) + 1):
        text = PROMPT[:i] + ("|" if i < len(PROMPT) else "")
        frames.append((render([], theme, prompt=text, status=None), 70))
    for dots in ("···", "···", "···"):
        frames.append(
            (
                render(
                    [],
                    theme,
                    prompt=PROMPT,
                    status=f"√ Agent 已连接 jobfindsme · 本地解析简历并双平台并行检索{dots}",
                ),
                420,
            )
        )
    visible: list[tuple[str, str]] = []
    for group in _visible_groups():
        visible += group
        frames.append(
            (
                render(
                    visible,
                    theme,
                    prompt=PROMPT,
                    status="√ 双平台检索完成 · 共 102 条 · 过滤后 8 条",
                ),
                950,
            )
        )
    frames.append(
        (
            render(
                visible,
                theme,
                prompt=PROMPT,
                status="√ 双平台检索完成 · 共 102 条 · 过滤后 8 条",
            ),
            2400,
        )
    )
    return frames


def _to_rgb(img: Image.Image, theme: Theme) -> Image.Image:
    bg = Image.new("RGB", img.size, theme.page)
    bg.paste(img, mask=img.split()[3])
    return bg


def _final_lines() -> list[tuple[str, str]]:
    visible: list[tuple[str, str]] = []
    for group in _visible_groups():
        visible += group
    return visible


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    for theme, gif_name, png_name in (
        (DARK, "demo-dark.gif", "screenshot-dark.png"),
        (LIGHT, "demo-light.gif", "screenshot-light.png"),
    ):
        scenes = scenes_for(theme)
        first, rest = scenes[0], scenes[1:]
        first[0].save(
            DOCS / gif_name,
            save_all=True,
            append_images=[img for img, _ in rest],
            duration=[first[1], *(ms for _, ms in rest)],
            loop=0,
            optimize=True,
        )
        final = render(
            _final_lines(),
            theme,
            prompt=PROMPT,
            status="√ 双平台检索完成 · 共 102 条 · 过滤后 8 条",
        )
        final.save(DOCS / png_name)
    print(
        "Rendered demo-dark.gif, demo-light.gif, screenshot-dark.png, screenshot-light.png"
    )


if __name__ == "__main__":
    main()
