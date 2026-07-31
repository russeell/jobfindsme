#!/usr/bin/env python3
"""Generate jobfindsme README hero images via HTML/CSS + Chrome headless.

More reliable than PIL drawing: real browser typography, emoji, shadows,
and mature terminal color schemes. Reproducible — no manual recording.

Outputs:
  docs/search-results.png — 1200x630 hero
  docs/demo.gif           — terminal typing/result animation

Requires: Google Chrome (headless), Pillow.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ── Tokyo Night terminal palette ─────────────────────────────────────────────
BG = "#1a1b26"       # editor background
FG = "#c0caf5"       # foreground
DIM = "#565f89"      # comment
GREEN = "#9ece6a"    # success
BLUE = "#7aa2f7"     # prompt / links
PURPLE = "#bb9af7"   # accent
YELLOW = "#e0af68"   # warning
RED = "#f7768e"

FONT_STACK = (
    '"SF Mono", Menlo, Monaco, "JetBrains Mono", "Cascadia Code", monospace'
)
CJK_STACK = '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'


def page(
    *,
    terminal_lines: list[str],
    brand: bool = True,
    width: int = 1200,
    height: int = 630,
) -> str:
    """Single HTML document: optional left brand panel + terminal window."""
    term_html = "\n".join(terminal_lines)
    brand_html = ""
    if brand:
        brand_html = f"""
        <div class="brand">
          <div class="logo-row">
            <div class="logo">J</div>
            <div>
              <div class="logo-name">jobfindsme</div>
              <div class="logo-sub">AI 求职雷达 · MCP Server</div>
            </div>
          </div>
          <div class="scenarios">
            <div class="scenario"><span class="sc-num">01</span><div><div class="sc-title">找岗位</div><div class="sc-desc">一句话匹配岗位 + 投递链接</div></div></div>
            <div class="scenario"><span class="sc-num">02</span><div><div class="sc-title">定时推送</div><div class="sc-desc">任意时间频率，投递过的不重推</div></div></div>
            <div class="scenario"><span class="sc-num">03</span><div><div class="sc-title">查历史</div><div class="sc-desc">所有匹配过的岗位随时可查</div></div></div>
          </div>
          <div class="tags">
            <span>BOSS直聘</span><span>猎聘</span><span>本地优先</span><span>无 API Key</span>
          </div>
          <div class="tagline">对 Agent 说一句话，剩下的交给它</div>
        </div>
        """
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px; height: {height}px;
    font-family: {CJK_STACK};
    background: radial-gradient(1200px 600px at 30% 0%, #161b2b 0%, #0b0e1a 100%);
    display: flex; align-items: center; justify-content: center;
    gap: 48px; overflow: hidden;
  }}
  .brand {{ width: 400px; color: #c0caf5; }}
  .logo-row {{ display: flex; align-items: center; gap: 14px; margin-bottom: 34px; }}
  .logo {{
    width: 52px; height: 52px; border-radius: 14px;
    background: linear-gradient(135deg, #7aa2f7, #bb9af7);
    display: flex; align-items: center; justify-content: center;
    font-family: {FONT_STACK}; font-size: 28px; font-weight: 700;
    color: #0b0e1a; box-shadow: 0 8px 24px rgba(122,162,247,.35);
  }}
  .logo-name {{ font-size: 26px; font-weight: 700; letter-spacing: .3px; }}
  .logo-sub {{ font-size: 13px; color: #565f89; margin-top: 2px; }}
  .scenarios {{ display: flex; flex-direction: column; gap: 18px; margin-bottom: 30px; }}
  .scenario {{ display: flex; gap: 14px; align-items: flex-start; }}
  .sc-num {{
    font-family: {FONT_STACK}; font-size: 13px; font-weight: 700;
    color: #7aa2f7; background: rgba(122,162,247,.12);
    padding: 4px 8px; border-radius: 8px;
  }}
  .sc-title {{ font-size: 17px; font-weight: 600; }}
  .sc-desc {{ font-size: 13px; color: #565f89; margin-top: 2px; }}
  .tags {{ display: flex; gap: 8px; margin-bottom: 26px; flex-wrap: wrap; }}
  .tags span {{
    font-size: 12px; color: #a9b1d6; background: #1f2335;
    border: 1px solid #2f3450; padding: 4px 10px; border-radius: 999px;
  }}
  .tagline {{ font-size: 14px; color: #7aa2f7; font-weight: 500; }}
  .terminal {{
    width: 660px; border-radius: 14px; overflow: hidden;
    background: {BG}; border: 1px solid #2f3450;
    box-shadow: 0 24px 60px rgba(0,0,0,.55), 0 2px 8px rgba(0,0,0,.4);
  }}
  .term-bar {{
    height: 38px; background: #16161e; display: flex; align-items: center;
    padding: 0 14px; gap: 8px; border-bottom: 1px solid #2f3450;
  }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .term-title {{
    margin-left: 10px; font-family: {FONT_STACK}; font-size: 12px;
    color: #565f89;
  }}
  .term-body {{
    padding: 16px 18px 18px; font-family: {FONT_STACK};
    font-size: 14.5px; line-height: 1.75; color: {FG};
  }}
  .p {{ color: {GREEN}; }}          /* prompt arrow */
  .in {{ color: {FG}; }}            /* user input */
  .u  {{ color: {BLUE}; }}          /* 'user:' label */
  .dim {{ color: {DIM}; }}
  .ok {{ color: {GREEN}; }}
  .link {{ color: {BLUE}; text-decoration: none; }}
  .job {{ color: {FG}; }}
  .hl {{ color: {PURPLE}; }}
  .sep {{ color: {DIM}; }}
</style></head>
<body>
  {brand_html}
  <div class="terminal">
    <div class="term-bar">
      <span class="dot" style="background:#ff5f56"></span>
      <span class="dot" style="background:#ffbd2e"></span>
      <span class="dot" style="background:#27c93f"></span>
      <span class="term-title">jobfindsme — zsh</span>
    </div>
    <div class="term-body">
{term_html}
    </div>
  </div>
</body></html>"""


def term_line(html: str) -> str:
    return f'      <div>{html}</div>'


def prompt(text: str) -> str:
    return term_line(f'<span class="p">❯ </span><span class="in">{text}</span>')


def user(text: str) -> str:
    return term_line(
        f'<span class="u">user:</span> <span class="in">{text}</span>'
    )


def job(num: str, title: str, company: str, loc: str, salary: str) -> str:
    return term_line(
        f'<span class="job">{num}. {title}</span>'
        f'<span class="sep"> ｜ </span><span class="job">{company}</span>'
        f'<span class="sep"> ｜ </span><span class="dim">{loc}</span>'
        f'<span class="sep"> ｜ </span><span class="hl">{salary}</span>'
    )


def screenshot(html: str, out: Path, width: int, height: int) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        tmp = f.name
    try:
        subprocess.run(
            [
                CHROME, "--headless=new", "--disable-gpu",
                f"--window-size={width},{height}",
                f"--screenshot={out}", f"file://{tmp}",
            ],
            check=True, capture_output=True, timeout=60,
        )
    finally:
        os.unlink(tmp)


# ── hero PNG ─────────────────────────────────────────────────────────────────


def hero_lines() -> list[str]:
    return [
        user("用 jobfindsme 根据简历找上海的 AI 应用工程师，20K以上"),
        term_line(
            '<span class="dim">→ 搜索 </span>'
            '<span class="ok">BOSS直聘·上海 ✓</span><span class="dim"> · </span>'
            '<span class="ok">猎聘·上海 ✓</span>'
            '<span class="dim"> (4.2s)</span>'
        ),
        term_line('<span class="ok">🆕 新增 6 个匹配岗位（已过滤 42 → 20）</span>'),
        job("1", "AI应用工程师（Agent开发）", "某知名公司", "上海", "40K-60K"),
        job("2", "AI应用工程师", "上汽云计算中心", "上海", "25K-40K"),
        job("3", "AI应用工程师（CAD方向）", "极芯拓方", "上海浦东", "40K-70K"),
        job("4", "AI应用工程师", "某上海基金公司", "上海", "20K-28K"),
        term_line(
            '<span class="dim">投递链接: </span>'
            '<span class="link">https://www.liepin.com/job/1980438233.shtml</span>'
        ),
        term_line(
            '<span class="dim">投递后说「</span><span class="in">标记第 2 个为已投递</span>'
            '<span class="dim">」— 明天自动跳过</span>'
        ),
    ]


def render_hero(path: Path) -> None:
    html = page(terminal_lines=hero_lines(), brand=True)
    screenshot(html, path, 1200, 630)
    print(f"✓ {path}")


# ── demo GIF ────────────────────────────────────────────────────────────────


def render_gif(path: Path) -> None:
    from PIL import Image

    W, H = 1100, 700
    request = "用 jobfindsme 根据简历找上海的 AI 应用工程师，20K以上"
    frames: list[Path] = []
    delay_ms = 550

    def frame(lines: list[str], name: str) -> Path:
        p = Path(tempfile.mkdtemp()) / f"{name}.png"
        html = page(terminal_lines=lines, brand=False, width=W, height=H)
        screenshot(html, p, W, H)
        frames.append(p)
        return p

    # Scene 1 — typing
    for i in range(1, 6):
        frame([prompt(request[: len(request) * i // 5])], f"t{i}")
    frame([prompt(request)], "t5b")

    # Scene 2 — results appear
    base = [
        prompt(request),
        term_line(
            '<span class="dim">→ 搜索 </span><span class="ok">BOSS直聘·上海 ✓</span>'
            '<span class="dim"> · </span><span class="ok">猎聘·上海 ✓</span>'
            '<span class="dim"> (4.2s)</span>'
        ),
    ]
    jobs = [
        job("1", "AI应用工程师（Agent开发）", "某知名公司", "上海", "40K-60K"),
        job("2", "AI应用工程师", "上汽云计算中心", "上海", "25K-40K"),
        job("3", "AI应用工程师（CAD方向）", "极芯拓方", "上海浦东", "40K-70K"),
    ]
    frame(base + [term_line('<span class="ok">🆕 新增 6 个匹配岗位</span>')], "r0")
    for i in range(1, len(jobs) + 1):
        frame(base + [term_line('<span class="ok">🆕 新增 6 个匹配岗位</span>')] + jobs[:i], f"r{i}")

    # Scene 3 — mark applied
    for i in range(1, 5):
        frame(
            base + jobs + [prompt("把第 2 个标记为已投递"[: len("把第 2 个标记为已投递") * i // 4])],
            f"a{i}",
        )
    frame(
        base + jobs
        + [prompt("把第 2 个标记为已投递"),
           term_line('<span class="ok">✓ 已投递：AI应用工程师 ｜上汽云计算中心（明天推送自动跳过）</span>')],
        "a5",
    )

    # Scene 4 — schedule
    for i in range(1, 5):
        frame(
            base[:1] + jobs[:2]
            + [prompt("每天早上 9 点推送新岗位给我"[: len("每天早上 9 点推送新岗位给我") * i // 4])],
            f"s{i}",
        )
    frame(
        base[:1] + jobs[:2]
        + [prompt("每天早上 9 点推送新岗位给我"),
           term_line('<span class="ok">✓ 已设置：每天 09:00 推送 · 只看新增 · 已投递不重推</span>')],
        "s5",
    )

    # Scene 5 — history
    for i in range(1, 4):
        frame(
            [prompt("我投过哪些岗位？"[: len("我投过哪些岗位？") * i // 3])],
            f"h{i}",
        )
    frame(
        [prompt("我投过哪些岗位？"),
         term_line('<span class="ok">📋 已投递 3 个岗位（最近优先）：</span>'),
         term_line('<span class="hl">  · AI应用工程师 ｜上汽云计算中心 ｜07-31 已投递</span>'),
         term_line('<span class="hl">  · AI应用工程师 ｜某上海基金公司 ｜07-30 已投递</span>')],
        "h4",
    )

    images = [Image.open(p) for p in frames]
    images[0].save(
        path, save_all=True, append_images=images[1:],
        duration=delay_ms, loop=0,
    )
    for p in frames:
        p.unlink(missing_ok=True)
    print(f"✓ {path} ({len(images)} 帧, {os.path.getsize(path)//1024} KB)")


if __name__ == "__main__":
    docs = Path(__file__).resolve().parents[1] / "docs"
    render_hero(docs / "search-results.png")
    render_gif(docs / "demo.gif")
