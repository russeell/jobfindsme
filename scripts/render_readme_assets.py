"""Render README screenshots from the fixed jobfindsme output contract.

The assets intentionally use a deterministic sample instead of a live job
search.  This keeps README images reproducible while still showing the exact
five-section response shape returned by the MCP server.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FONT_PATHS = (
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
)

BG = "#0b0f14"
PANEL = "#111827"
SECTION_BG = "#10243f"
TEXT = "#e5edf7"
MUTED = "#93a4b8"
BLUE = "#60a5fa"
GREEN = "#7dd3a7"
YELLOW = "#f2c76b"
RULE = "#263244"
SOFT_RULE = "#1e293b"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT_TITLE = _font(25)
FONT_BODY = _font(22)
FONT_SMALL = _font(18)
FONT_BADGE = _font(17)


PROMPT = (
    "用 jobfindsme，根据 ~/Documents/resume.pdf，"
    "找上海和杭州的 AI 应用工程师岗位，20K以上，社招，正式。"
)

DEMO_LINES: list[tuple[str, str]] = [
    (
        "你",
        PROMPT,
    ),
    ("", ""),
    ("section", "【1·简历解析】"),
    ("body", "简历解析：技能 18 项 ｜ 项目 3 项 ｜ 经验 2 项 ｜ 学历：本科"),
    ("", ""),
    ("section", "【2·检索概览】"),
    (
        "good",
        "检索：猎聘·上海 成功(42) · BOSS直聘·上海 成功(30) · "
        "猎聘·杭州 成功(18) · BOSS直聘·杭州 成功(12)",
    ),
    ("body", "本轮远程发现 102 条，本地岗位库匹配到 12 条。"),
    ("", ""),
    ("section", "【3·过滤说明】"),
    (
        "body",
        "过滤：角色(AI应用工程师/Agent工程师) + 城市(上海/杭州) + "
        "薪资20K+ + 社招 + 正式 → 给出 8 个",
    ),
    ("", ""),
    ("section", "【4·岗位列表】"),
    ("job", "1. [新增] AI Agent应用工程师｜星河科技｜上海｜社招｜正式｜25-40K"),
    ("score", "   匹配度：92%（信号匹配，非录用概率）"),
    ("body", "   技能：RAG、Agent、FastAPI、MCP ｜ 经验：1-3年 ｜ 学历：本科"),
    ("", ""),
    (
        "link",
        "   投递链接：https://www.zhipin.com/job_detail/example-shanghai-ai-agent.html",
    ),
    ("", ""),
    (
        "body",
        "   推荐理由：简历事实与岗位信号综合匹配度为 92%；"
        "JD 明确涉及 RAG、Agent、FastAPI、MCP；薪资信息明确。",
    ),
    ("", ""),
    ("job", "2. [新增] 大模型应用开发工程师｜云帆智能｜杭州｜社招｜正式｜22-35K"),
    ("score", "   匹配度：87%（信号匹配，非录用概率）"),
    ("body", "   技能：LLM、工具调用、Reranker、pytest ｜ 经验：1-3年 ｜ 学历：本科"),
    ("warning", "   需要注意：JD 要求 Kubernetes，简历中未找到直接证据"),
    ("", ""),
    ("link", "   投递链接：https://www.liepin.com/job/example-hangzhou-llm-app.shtml"),
    ("", ""),
    (
        "body",
        "   推荐理由：简历事实与岗位信号综合匹配度为 87%；"
        "JD 明确涉及 LLM、工具调用、Reranker、pytest；薪资信息明确。",
    ),
    ("", ""),
    ("section", "【5·说明】"),
    (
        "body",
        "本次新增 8 个，变更 1 个，重开 0 个，关闭 2 个。"
        "已隐藏 24 个此前展示且未变化的岗位。",
    ),
]


def _color(kind: str) -> str:
    return {
        "你": BLUE,
        "section": GREEN,
        "good": GREEN,
        "job": TEXT,
        "score": BLUE,
        "link": BLUE,
        "warning": YELLOW,
    }.get(kind, TEXT)


def _prompt_frame(text: str) -> list[tuple[str, str]]:
    cursor = "  ▌" if len(text) < len(PROMPT) else ""
    return [("你", text + cursor)]


def _with_status(lines: list[tuple[str, str]], status: str) -> list[tuple[str, str]]:
    return [*lines, ("", ""), ("good", status)]


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    width: int,
) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if draw.textlength(candidate, font=font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def render(
    lines: list[tuple[str, str]],
    *,
    width: int = 1180,
    height: int = 900,
) -> Image.Image:
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    margin = 34
    radius = 20
    draw.rounded_rectangle(
        (margin, margin, width - margin, height - margin),
        radius=radius,
        fill=PANEL,
        outline=RULE,
        width=1,
    )
    draw.text((margin + 34, margin + 28), "jobfindsme", fill=TEXT, font=FONT_TITLE)
    draw.rounded_rectangle(
        (margin + 190, margin + 27, margin + 330, margin + 58),
        radius=15,
        fill=SECTION_BG,
    )
    draw.text(
        (margin + 209, margin + 34),
        "固定五段输出",
        fill=BLUE,
        font=FONT_BADGE,
    )
    draw.line(
        (margin + 34, margin + 76, width - margin - 34, margin + 76),
        fill=SOFT_RULE,
        width=1,
    )

    y = margin + 100
    x = margin + 34
    max_width = width - margin * 2 - 68
    line_gap = 9
    for kind, text in lines:
        if not text:
            y += 9
            continue
        font = FONT_BODY if kind not in {"section", "你"} else FONT_TITLE
        prefix = (
            ""
            if kind in {"section", "body", "job", "score", "link", "warning", "good"}
            else f"{kind}："
        )
        wrapped = _wrap(draw, prefix + text, font, max_width)
        for line in wrapped:
            if y > height - margin - 38:
                draw.text((x, height - margin - 36), "…", fill=MUTED, font=FONT_BODY)
                return img
            draw.text((x, y), line, fill=_color(kind), font=font)
            y += font.size + line_gap
    return img


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    full = render(DEMO_LINES, width=1280, height=1280)
    full.save(DOCS / "search-results.png", quality=95)

    screenshot = render(DEMO_LINES, width=1180, height=1200)
    screenshot.save(DOCS / "search-screenshot.png", quality=95)

    scenes = [
        _prompt_frame("用 jobfindsme"),
        _prompt_frame("用 jobfindsme，根据 ~/Documents/resume.pdf"),
        _prompt_frame(PROMPT),
        _with_status(DEMO_LINES[:4], "Agent 正在解析简历并生成搜索条件…"),
        _with_status(DEMO_LINES[:8], "双平台并行检索中：猎聘 + BOSS直聘…"),
        DEMO_LINES[:13],
        DEMO_LINES[:21],
        DEMO_LINES[:30],
        DEMO_LINES,
    ]
    frames = [render(scene, width=1000, height=1220) for scene in scenes]
    frames[0].save(
        DOCS / "demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=[650, 800, 900, 950, 1050, 1150, 1400, 1700, 3600],
        loop=0,
        optimize=True,
    )

    print("Rendered docs/search-screenshot.png, docs/search-results.png, docs/demo.gif")


if __name__ == "__main__":
    main()
