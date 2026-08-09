"""Turn captured real MCP output into a designed demo page (dark/light).

The page is a modern chat-style UI: user prompt bubble, then the five
sections rendered as cards with score badges, source chips, filter chips,
job cards and the operating summary.  Browsers render it with system fonts
(PingFang SC / Hiragino) so the result is crisp instead of pixel art.
"""

# ruff: noqa: E501  # embedded CSS/HTML/JS lines are intentionally long

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

CSS = """
:root{--bg:#050708;--win:#080b0d;--win2:#0b0f12;--card:#0f1418;--card2:#12191e;
--line:#253038;--text:#f4f7f8;--muted:#8b9aa3;--blue:#58c8ff;--green:#b9f227;
--amber:#ffcb5c;--red:#ff7171;--chip:rgba(88,200,255,.11);--chip2:rgba(185,242,39,.11);
--grad:linear-gradient(135deg,#b9f227,#74df73)}
body[data-theme="light"]{--bg:#edf1f6;--win:#ffffff;--win2:#f7f9fc;--card:#f7f9fc;
--card2:#ffffff;--line:#e3e9f1;--text:#101828;--muted:#5f6f82;--blue:#2563eb;
--green:#059669;--amber:#d97706;--red:#dc2626;--chip:rgba(37,99,235,.09);
--chip2:rgba(5,150,105,.10);--grad:linear-gradient(135deg,#1d4ed8,#3b82f6)}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--bg);font-family:"PingFang SC","Hiragino Sans GB",
"Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;color:var(--text);
display:block;padding:0}
.win{width:1280px;border-radius:18px;background:var(--win);border:1px solid var(--line);
box-shadow:0 24px 70px rgba(0,0,0,.55);overflow:hidden}
body[data-theme="light"] .win{box-shadow:0 22px 60px rgba(15,23,42,.14)}
.bar{display:flex;align-items:center;gap:14px;padding:18px 28px;background:var(--win2);
border-bottom:1px solid var(--line)}
.dot{width:12px;height:12px;border-radius:50%}
.brand{font-weight:700;font-size:17px;display:flex;align-items:center;gap:10px}
.logo{width:34px;height:34px;border-radius:9px;background:var(--grad);color:#071008;
display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:900;letter-spacing:-.4px}
.sub{color:var(--muted);font-weight:500;font-size:13px}
.pill{margin-left:auto;font-size:12px;color:var(--blue);background:var(--chip);
border:1px solid var(--line);padding:6px 12px;border-radius:999px;font-weight:600}
.body{padding:24px 28px 12px;display:flex;flex-direction:column;gap:14px}
.user{display:flex;gap:12px;align-items:flex-start}
.avatar{flex:none;width:36px;height:36px;border-radius:10px;background:var(--green);
color:#071008;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800}
.bubble{background:#10171b;color:var(--text);border:1px solid #34424b;border-left:3px solid var(--green);
border-radius:5px 14px 14px 14px;padding:12px 16px;font-size:15px;line-height:1.6;
max-width:920px;min-height:22px}
.status{display:none;color:var(--green);font-size:13px;padding-left:48px;font-weight:600}
.status.on{display:block}
.dots{display:inline-block;animation:blink 1.2s steps(1) infinite}
@keyframes blink{0%,40%{opacity:1}41%,100%{opacity:.25}}
.card{opacity:0;transform:translateY(12px);transition:opacity .5s ease,transform .5s ease}
.card.vis{opacity:1;transform:none}
.job,.more{opacity:0;transform:translateY(8px);transition:opacity .45s ease,transform .45s ease}
.job.vis,.more.vis{opacity:1;transform:none}
.sec{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px 17px}
.sec h3{font-size:13px;color:var(--green);font-weight:700;letter-spacing:.2px;
display:flex;align-items:center;gap:8px;margin-bottom:10px}
.sec h3::before{content:"";width:8px;height:8px;border-radius:3px;background:var(--green)}
.stats{display:flex;gap:10px;flex-wrap:wrap}
.stat{background:var(--card2);border:1px solid var(--line);border-radius:8px;
padding:7px 12px;font-size:13px;color:var(--muted)}
.stat b{color:var(--text)}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{font-size:12.5px;padding:6px 11px;border-radius:8px;background:var(--chip);
color:var(--blue);font-weight:600}
.chip.ok{background:var(--chip2);color:var(--green)}
.chip.warn{background:rgba(251,191,36,.13);color:var(--amber)}
.caption{font-size:12.5px;color:var(--muted);margin-top:9px}
.job{border:1px solid var(--line);border-radius:11px;background:var(--card2);
padding:14px 15px;margin-bottom:10px;min-height:184px;display:flex;flex-direction:column}
.jobs{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.jobs .job{margin-bottom:0}
.jobs .reason{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.job .top{display:flex;align-items:center;gap:10px}
.tag{font-size:11px;font-weight:700;padding:3px 8px;border-radius:7px;background:var(--chip2);color:var(--green)}
.job h4{font-size:14.5px;font-weight:750;color:var(--text);flex:1;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.score{margin-left:auto;font-size:12.5px;font-weight:800;padding:5px 11px;border-radius:999px}
.score.g{background:var(--chip2);color:var(--green)}
.score.b{background:var(--chip);color:var(--blue)}
.score.a{background:rgba(251,191,36,.13);color:var(--amber)}
.company{font-size:12.5px;color:var(--muted);margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.salary{font-size:15px;font-weight:800;color:var(--green);margin-top:7px}
.meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}
.tag-s{font-size:11.5px;padding:3px 9px;border-radius:7px;background:var(--chip);color:var(--blue)}
.tag-s.n{background:rgba(248,113,113,.12);color:var(--red)}
.link{margin-top:auto;padding-top:9px;font-size:12px;color:var(--blue);font-weight:700}
.link .domain{color:var(--muted);font-weight:500;margin-left:6px}
.reason{margin-top:7px;font-size:12.3px;color:var(--muted);line-height:1.55}
.more{border:1px dashed var(--line);border-radius:12px;padding:10px 14px;font-size:12.5px;
color:var(--muted);text-align:center}
.summary{display:grid;gap:8px}
.summary .row{font-size:13px;line-height:1.6}
.summary .row b{color:var(--text)}
.summary .row.hl{background:var(--chip);border:1px solid var(--line);border-radius:10px;padding:9px 12px}
.summary ul{list-style:none;display:flex;flex-direction:column;gap:5px;font-size:12.8px;color:var(--muted)}
.foot{display:flex;justify-content:center;gap:22px;padding:14px 20px;border-top:1px solid var(--line);
margin-top:14px;font-size:12px;color:var(--muted)}
.foot span::before{content:"·";margin-right:10px;color:var(--blue);font-weight:700}
.foot span:first-child::before{content:"";margin:0}
"""


def esc(value: str) -> str:
    return html.escape(value, quote=False)


def parse_sources(line: str) -> list[dict]:
    sources = []
    for part in re.split(r"\s+·\s+", line):
        part = part.strip()
        current = re.match(r"(.+?)\s+([✓△✗-])\s+(.+)$", part)
        legacy = re.match(r"(.+?)\s+([✓△✗-])\((.*)\)$", part)
        match = current or legacy
        if match:
            marker = match.group(2)
            sources.append(
                {
                    "name": match.group(1),
                    "state": "ok" if marker == "✓" else "warn",
                    "count": match.group(3),
                }
            )
        else:
            sources.append({"name": part, "state": "muted", "count": ""})
    return sources


def parse_jobs(section: str) -> list[dict]:
    jobs = []
    job: dict | None = None
    for line in section.splitlines():
        head = re.match(r"^(\d+)\.\s+(?:\[([^\]]+)\])?\s*(.*)$", line)
        if head:
            if job:
                jobs.append(job)
            fields = [part.strip() for part in head.group(3).split("｜")]
            job = {
                "index": int(head.group(1)),
                "tag": head.group(2) or "",
                "title": fields[0] if fields else "",
                "company": fields[1] if len(fields) > 1 else "",
                "city": fields[2] if len(fields) > 2 else "",
                "salary": fields[-1] if len(fields) > 3 else "",
                "score": 0,
                "skills": [],
                "exp": "",
                "degree": "",
                "link": "",
                "reason": "",
            }
            continue
        if job is None:
            continue
        score = re.search(r"匹配度：(\d+)%", line)
        skills = re.search(r"技能：([^｜]+)", line)
        exp = re.search(r"经验：([^｜]+)", line)
        degree = re.search(r"学历：([^｜]+)", line)
        link = re.search(r"投递链接：(\S+)", line)
        reason = re.search(r"推荐理由：(.+)", line)
        if score:
            job["score"] = int(score.group(1))
        if skills:
            job["skills"] = [s.strip() for s in skills.group(1).split("、")][:4]
        if exp:
            job["exp"] = exp.group(1).strip()
        if degree:
            job["degree"] = degree.group(1).strip()
        if link:
            job["link"] = link.group(1)
        if reason:
            job["reason"] = reason.group(1).strip()
    if job:
        jobs.append(job)
    return jobs


def parse(text: str) -> dict:
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("【"):
            if current:
                sections.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    parsed: dict = {
        "stats": [],
        "sources": [],
        "filters": [],
        "jobs": [],
        "summary": [],
    }
    for block in sections:
        lines = block.splitlines()
        header = lines[0] if lines else ""
        if "简历解析" in header:
            m = re.search(
                r"技能 (\d+) 项.*?项目 (\d+) 项.*?经验 (\d+) 项.*?学历：(\S+)", block
            )
            if m:
                parsed["stats"] = [
                    ("技能", m.group(1)),
                    ("项目", m.group(2)),
                    ("经验", m.group(3)),
                    ("学历", m.group(4)),
                ]
        elif "检索概览" in header:
            for line in lines[1:]:
                if line.startswith("检索"):
                    parsed["sources"] = parse_sources(line[3:])
                elif line.startswith(("覆盖", "本轮", "远程")):
                    parsed["source_caption"] = line.strip()
        elif "过滤说明" in header:
            for line in lines[1:]:
                m = re.match(r"过滤：(.*?) → 给出 (\d+) 个", line)
                if m:
                    parsed["filters"] = [f.strip() for f in m.group(1).split(" + ")]
                    parsed["result_count"] = m.group(2)
        elif "岗位列表" in header:
            parsed["jobs"] = parse_jobs(block.split("\n", 1)[1])
        elif "说明" in header:
            parsed["summary"] = [line.strip() for line in lines[1:] if line.strip()]
    return parsed


def score_class(score: int) -> str:
    if score >= 90:
        return "g"
    if score >= 80:
        return "b"
    return "a"


def source_label(link: str) -> tuple[str, str]:
    host = urlsplit(link).netloc.removeprefix("www.")
    if "zhipin" in host:
        return "BOSS直聘", host
    if "liepin" in host:
        return "猎聘", host
    if "zhaopin" in host:
        return "智联招聘", host
    if "51job" in host:
        return "前程无忧", host
    return "查看岗位", host


def evidence_line(job: dict) -> str:
    if job["skills"]:
        return "技能证据：" + " / ".join(job["skills"])
    return "硬条件证据：角色、城市、薪资与招聘类型符合"


def render(data: dict, theme: str) -> str:
    p = data["parsed"]

    stats = "".join(
        f'<div class="stat">{esc(k)} <b>{esc(v)}</b></div>' for k, v in p["stats"]
    )
    chips = "".join(
        f'<span class="chip {"ok" if s["state"] == "ok" else "warn" if s["state"] == "warn" else ""}">'
        f"{esc(s['name'])} {s['count']}</span>"
        for s in p["sources"]
    )
    caption_text = p.get("source_caption", "")
    top_counts = data.get("top_counts", {})
    if top_counts:
        distribution = "、".join(
            f"{name} {count}" for name, count in top_counts.items() if count
        )
        if distribution:
            caption_text += f" 入选 Top {sum(top_counts.values())}：{distribution}。"
    caption = esc(caption_text)
    filters = "".join(f'<span class="chip">{esc(f)}</span>' for f in p["filters"])

    jobs = []
    for job in p["jobs"]:
        source, domain = source_label(job["link"])
        evidence = evidence_line(job)
        tag = f'<span class="tag">{esc(job["tag"])}</span>' if job["tag"] else ""
        skills = "".join(f'<span class="tag-s">{esc(s)}</span>' for s in job["skills"])
        exp = f'<span class="tag-s">{esc(job["exp"])}</span>' if job["exp"] else ""
        degree = (
            f'<span class="tag-s">{esc(job["degree"])}</span>' if job["degree"] else ""
        )
        jobs.append(
            f'<div class="job" id="job-{job["index"]}"><div class="top">{tag}<h4>{esc(job["title"])}'
            f"</h4>"
            f'<span class="score {score_class(job["score"])}">{job["score"]}%</span></div>'
            f'<div class="company">{esc(job["company"])} · {esc(job["city"])}</div>'
            f'<div class="salary">{esc(job["salary"])}</div>'
            f'<div class="meta">{skills}{exp}{degree}</div>'
            f'<div class="reason">{esc(evidence)}</div>'
            f'<div class="link">{esc(source)} · 查看岗位 ↗<span class="domain">{esc(domain)}</span></div></div>'
        )
    job_list = f'<div class="jobs">{"".join(jobs[:8])}</div>'
    total = int(p.get("result_count", len(p["jobs"])))
    extra = max(0, total - 8)
    more = (
        f'<div class="more" id="more">本轮共 {total} 个匹配岗位 · 下方省略 {extra} 个 · 实际输出均含完整投递链接</div>'
        if extra > 0
        else ""
    )

    summary_rows = []
    for line in p["summary"]:
        if line.startswith("结果"):
            summary_rows.append(f'<div class="row"><b>{esc(line)}</b></div>')
        elif line.startswith("建议"):
            summary_rows.append(f'<div class="row hl">{esc(line)}</div>')
        elif line.startswith("下一步"):
            summary_rows.append(
                f'<div class="row" style="color:var(--muted)">{esc(line)}</div>'
            )
        elif line.startswith("-"):
            summary_rows.append(f"<ul><li>{esc(line)}</li></ul>")
        else:
            summary_rows.append(
                f'<div class="row" style="color:var(--muted)">{esc(line)}</div>'
            )
    summary = "".join(summary_rows)

    html_doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body data-theme="{theme}">
<div class="win">
  <div class="bar">
    <span class="dot" style="background:#f87171"></span>
    <span class="dot" style="background:#fbbf24"></span>
    <span class="dot" style="background:#34d399"></span>
    <div class="brand"><span class="logo">jfm</span>jobfindsme<span class="sub">AI 求职雷达</span></div>
    <div class="pill">4 平台 · 本地优先 · MCP Server</div>
  </div>
  <div class="body">
    <div class="user"><div class="avatar">你</div><div class="bubble" id="prompt"></div></div>
    <div class="status" id="status">正在连接 jobfindsme · 本地解析简历并四平台并行检索<span class="dots">…</span></div>
    <div class="card" id="s1"><div class="sec"><h3>① 简历解析</h3><div class="stats">{stats}</div></div></div>
    <div class="card" id="s2"><div class="sec"><h3>② 检索概览</h3><div class="chips">{chips}</div><div class="caption">{caption}</div></div></div>
    <div class="card" id="s3"><div class="sec"><h3>③ 过滤说明</h3><div class="chips">{filters}</div></div></div>
    <div class="card" id="s4"><div class="sec"><h3>④ 岗位列表</h3>{job_list}{more}</div></div>
    <div class="card" id="s5"><div class="sec"><h3>⑤ 说明</h3><div class="summary">{summary}</div></div></div>
  </div>
  <div class="foot"><span>本地优先</span><span>简历不出本机</span><span>SQLite 持久化</span><span>无需模型 API</span></div>
</div>
<script>
const PROMPT = {json.dumps(data["prompt"], ensure_ascii=False)};
const els = {{prompt: document.getElementById("prompt"), status: document.getElementById("status")}};
function full() {{
  ["s1","s2","s3","s4","s5"].forEach(id => document.getElementById(id).classList.add("vis"));
  document.querySelectorAll(".job, .more").forEach(el => el.classList.add("vis"));
  els.prompt.textContent = PROMPT; els.status.classList.add("on");
}}
if (window.__SKIP_TO_END__) {{ full(); }}
else {{
  let i = 0;
  function type() {{
    els.prompt.textContent = PROMPT.slice(0, i) + (i < PROMPT.length ? "▍" : "");
    if (i <= PROMPT.length) {{ i += 1; setTimeout(type, 48); }}
    else {{ setTimeout(() => {{ els.status.classList.add("on"); setTimeout(startReveal, 1050); }}, 260); }}
  }}
  function startReveal() {{
    const queue = [];
    ["s1","s2","s3","s4"].forEach(id => queue.push(document.getElementById(id)));
    document.querySelectorAll(".job").forEach(el => queue.push(el));
    const more = document.getElementById("more");
    if (more) queue.push(more);
    queue.push(document.getElementById("s5"));
    let t = 0;
    for (const el of queue) {{ t += 430;
      setTimeout(() => el.classList.add("vis"), t);
    }}
  }}
  type();
}}
</script></body></html>"""
    return html_doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_in", type=Path)
    parser.add_argument("html_out", type=Path)
    parser.add_argument("--theme", choices=("dark", "light"), required=True)
    args = parser.parse_args()
    data = json.loads(args.json_in.read_text(encoding="utf-8"))
    data["parsed"] = parse(data["text"])
    args.html_out.write_text(render(data, args.theme), encoding="utf-8")
    print(f"rendered {args.html_out}")


if __name__ == "__main__":
    main()
