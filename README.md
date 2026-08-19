<div align="center">

# jobfindsme · AI Job Search Radar

**One sentence brings together jobs from BOSS直聘, 猎聘 (Liepin), 智联招聘 and 前程无忧, then filters and tracks them against your resume — from inside any MCP-capable agent.**

<p>
  <a href="https://github.com/russeell/jobfindsme/actions/workflows/ci.yml"><img src="https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-stdio-111111" alt="MCP stdio">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT"></a>
  <img src="https://img.shields.io/badge/stars-welcome-yellow" alt="Stars welcome">
</p>

[中文](README.zh.md) · [Architecture](docs/architecture.md) · [Sources report](evaluation/evidence/latest_four_source_search.md)

</div>

---

> Install a local job-search MCP server for Claude Code, Codex, Cursor, and any
> MCP-capable agent. **Your agent does the talking — jobfindsme does the
> searching, filtering, and tracking.**

---

## Why

The annoying part of a daily job search is not "knowing how to search". It is
this repeated grunt work:

| Problem | What jobfindsme does |
|---|---|
| Switching between platforms | Searches four sources in one call; a failing source is reported explicitly while others still run |
| Floods of irrelevant results | Hard-filters role, city, salary, social/campus track, full-time/internship, then ranks |
| Seeing the same jobs again | Remembers what you saw, applied to, and ignored locally — only reports changes |
| Unexplained recommendations | Every job ships with a match score, evidence, gaps, and a direct apply link |
| API-key / account setup | No model API key needed; everything lives in a local SQLite database |

One sentence to start:

```text
Use jobfindsme with my local resume at ~/Documents/resume.pdf to find
AI application engineer roles in Shanghai, 20K+, experienced hiring, full-time.
```

---

## 🚀 Quick start

### Option 1: just ask your Agent (recommended)

In Claude Code, Codex, Cursor, or any agent, paste this whole sentence:

```text
Install jobfindsme by following the README at https://github.com/russeell/jobfindsme
```

The agent reads this README, installs the local runtime
(`curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh | bash`),
wires the MCP config, and asks you to restart. First install takes a few
minutes; if the agent cannot reach the network, use Option 2.
`install.sh` is published as a release asset, so this fixed URL always serves
the newest script (no CDN cache lag). CN fallback:
`https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh`
(jsdelivr cache may lag up to 12h after a push).

Once installed, just say what you need:

```text
Use my local resume at ~/Documents/resume.pdf to find AI application
engineer roles in Shanghai, 20K+.
```

### Option 2: manual (about 1 minute)

Install the local runtime once (Python 3.11+):

```bash
curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh | bash
```

Wire the MCP config to your Agent, then restart it:

```bash
jobfindsme connect             # auto-detect the current Agent (recommended)
jobfindsme connect claude      # Claude Code
jobfindsme connect codex       # Codex
jobfindsme connect cursor      # Cursor
```

Other MCP clients: `jobfindsme config` prints the standard JSON to paste, or
`jobfindsme connect --path <file>` writes it directly. The `.mcp.json` at the
repo root is the same standard config.

Self-check, then start:

```bash
jobfindsme doctor
```

The full resume is parsed by the local Core. Pass only its path to `setup` —
the agent must never read the whole file into the conversation.

BOSS直聘 needs a login: tell your agent "帮我登录 BOSS直聘" / "log in to BOSS".
It opens a dedicated Chrome window; scan the QR code once and keep the window
running. Skip this and the other sources still work.

### Native plugins (Codex / Claude Code)

One command installs the Skill + MCP config (the installer prints these at the end):

```bash
codex plugin marketplace add russeell/jobfindsme --ref main
codex plugin add jobfindsme@jobfindsme
```

```bash
claude plugin marketplace add russeell/jobfindsme
claude plugin install jobfindsme@jobfindsme
```

### Works with

Claude Code · Codex · Cursor · any MCP-compatible client — one standard MCP
config + one Skill serves them all.

---

## ✨ Capabilities

| Capability | What it means |
|---|---|
| One-sentence search | Agent calls the local MCP server; search config and results come back automatically |
| Four sources | BOSS直聘, 猎聘, 智联招聘, 前程无忧; failures are labeled, never hidden |
| Resume matching | Local PDF/MD/TXT parsing; ranks by skills, experience, education signals |
| Fact-grounded output | Server returns bounded structured facts + a five-section factual summary; the agent organizes the final wording |
| Incremental radar | Detects new, changed, reopened, closed jobs — no repeat recommendations |
| State memory | Save, applied, ignored; applied jobs are never re-suggested |
| Local-first | No model API key; resume and state stay in local SQLite |

### Evidence, not claims

| Release gate | Current result |
|---|---:|
| Python tests | 310 passing |
| Clean install + Cursor setup | 12 seconds |
| Agent behavior contract | 0/6 without the Skill, 6/6 with it |
| Wheel smoke test | CLI, SQLite migrations, and all 5 MCP tools pass end to end |

Live availability changes with platform controls and local login state.
jobfindsme never presents cache or a blocked response as fresh data; every
search returns per-source diagnostics. See the latest
[four-source search report](evaluation/evidence/latest_four_source_search.md).

---

## 💬 Use

Copy and adjust:

```text
# Find jobs
Use jobfindsme with ~/Documents/resume.pdf to find Beijing large-model
application engineer roles, 30K+, experienced hiring.

# Scheduled push
Push new jobs to me every morning at 9.

# History
Which jobs have I seen? Which have I applied to?

# New only
Keep finding jobs — only ones I haven't seen.

# Change conditions
Switch city to Shenzhen, salary floor to 25K, and search again.

# Manage state
Mark job #2 as applied; ignore all staffing-agency companies.
```

---

## 📦 Results

The Server decides facts, filtering, ranking, and evidence; the agent builds
the final answer from those facts. Each result returns bounded structured
facts (`structuredContent.jobs`) plus a five-section factual summary
(resume summary / search overview / filter note / job list / operating
summary) that the agent may adapt but must not contradict:

```text
AI应用工程师（Agent开发）｜示例科技｜上海｜社招｜正式｜25-40K
匹配度：92%（信号匹配，非录用概率）
技能：RAG、Agent、MCP ｜ 经验：1-3年 ｜ 学历：本科

投递链接：https://example.com/jobs/123

推荐理由：简历技能命中：RAG、Agent、MCP；综合匹配度为 92%；薪资信息明确。
需要注意：JD 要求 Kubernetes，简历中未找到直接证据
```

A job block always contains: **fact line + match score + blank line + bare
apply link + blank line + recommendation reason**. The score is a 60% hard-
condition floor (the job already passed role/city/salary/track/type) plus up
to 40% evidence bonus (skills > experience > education > liveness > salary
visibility). All shown jobs are in the 60–100% band, ordered by score.

Facts, scores, links, and reasons are generated deterministically by the
Server; the agent may not rewrite them in the initial response. Results are
never padded with weak matches, and missing fields are labeled, not guessed.

---

## 🌐 Sources

Four source paths are maintained — **BOSS直聘**, **猎聘 (Liepin)**,
**智联招聘**, and **前程无忧**. The project prioritizes reliable, useful
results over an inflated connector count and never claims complete coverage.

| Source | Method | Speed | Browser needed? |
|---|---|---|---|
| **BOSS直聘** | authorized local Chrome session, time-labeled cache fallback | login-dependent | yes |
| **猎聘** | public Web JSON listing, bounded detail enrichment | usually sub-second | no for listings |
| **智联招聘** | HTTP first, local-browser fallback after security checks | experimental | fallback only |
| **前程无忧** | HTTP first, local-browser fallback after WAF checks | experimental | fallback only |

> 智联招聘 / 前程无忧 are experimental: pure HTTP can be challenged by
> security checks in some networks. The system falls back to the authorized
> local browser; if still blocked, the source is explicitly marked failed
> while other sources keep returning results. Source count is not coverage —
> trust the per-search overview.

Connectors are pluggable; US/EU sources (Indeed, LinkedIn Jobs, …) are the
next frontier on the [roadmap](#-roadmap).

---

## ⚙️ How it works

```text
Agent (Claude / GPT / Qwen / WorkBuddy — interaction and follow-up talk)
  → MCP Server (local stdio)
  → Local Core
      → pure HTTP (猎聘 / 智联 / 前程无忧)
      → local Chrome CDP (BOSS直聘 inside its logged-in session)
      → fast mode: bounded concurrent refresh; one failing source never blocks others
  → normalize → cross-source dedup → hard filter (city/salary/track/type)
  → signal extraction + weighted coarse rank (skills/experience/education/liveness/salary)
  → incremental radar (new / changed / reopened / closed)
  → Server returns bounded facts + a five-section summary; the agent composes
    the answer from the facts (never inventing or dropping apply URLs)
```

The MCP Server owns hard filtering, structured signal extraction,
deterministic ranking, and the factual baseline. The agent owns natural
language; deeper comparison happens only when you ask, using the returned
evidence — never inventing facts or rewriting apply URLs.

Resumes, job state, and search plans live in local SQLite. Core needs no
model API.

---

## 🔒 Privacy & safety

- The full resume never enters the agent's context — only its local path goes to Core;
- job descriptions are untrusted external data, never instructions;
- exports write to local files; deletion uses a preview + confirmation-token protocol;
- no auto-apply, no CAPTCHA bypass, no claim of full market coverage.

---

## 🔧 Install & maintenance

**Update**: re-run the installer; the database migrates automatically and
history/state are kept:

```bash
curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh | bash
```

**Manual install** (when the script is unavailable): create a venv and install
the wheel from the [latest release](https://github.com/russeell/jobfindsme/releases/latest)
(`jobfindsme-X.Y.Z-py3-none-any.whl`):

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install --upgrade \
  "jobfindsme[browser] @ <latest wheel URL from releases/latest>"
```

**Uninstall**: `jobfindsme uninstall <host>` removes only the agent config,
never your data. To wipe everything, export first, then `rm -rf ~/.jobfindsme`.

---

## ❓ FAQ

**Q: Do all platforms need a login?**
Only BOSS (scan once; the local login state is reused). 猎聘 works over pure
HTTP with no browser.

**Q: Will my account get banned?**
This is low-frequency, human-paced reading — no bulk crawling, no auto-action.
Automated access is a gray area in platform terms, so account limits are
possible; use it personally at your own risk.

**Q: Why zero results / one platform is empty?**
Run `jobfindsme doctor`. BOSS checks the local Chrome and login state; 猎聘
checks the HTTP path. Degraded or failed sources are labeled explicitly —
never silently presented as "no jobs".

**Q: Is my resume uploaded?**
No. It is parsed locally into structured facts in SQLite; the raw text never
enters the agent context. `jobfindsme export` / `delete_local_data` export and
clear everything on demand.

**Q: What's the difference from just asking an AI to search?**
A generic agent has no platform access, no cross-day dedup or state memory,
and no stable PDF-to-facts parsing. jobfindsme makes those three things a
deterministic local service; the agent only talks.

**Q: Install taking more than 5 minutes?**
Stop it, keep the last output, and file an Issue. Do not let the agent clone
the repo, install dev dependencies, or download a whole browser to "fix" it.

---

## 🛣️ Roadmap

Direction, not commitments:

1. Stabilize the four Chinese sources (real-world availability over connector count);
2. Pluggable US/EU connectors (Indeed, LinkedIn Jobs, …) with the same gates;
3. Follow-up reminders (3/7/14 days after applying) and job-health signals
   (ghost-job detection) as local, deterministic features;
4. Scheduling/notification stays with the host agent — never auto-apply.

---

## 🛠 Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check . && ruff format --check .
```

Architecture, source gates, and the evaluation loop: [architecture](docs/architecture.md),
[connectors](docs/connectors.md), [evaluation](docs/evaluation.md); the full
engineering spec lives in `docs/internal/project_spec.md`. Report mis-ranked,
duplicated, or dead links via a sanitized
[Issue](https://github.com/russeell/jobfindsme/issues).

---

## ⚖️ Disclaimer

- Free, open-source personal tooling that organizes job info you are already
  logged in and entitled to see;
- automated access may trigger platform risk controls; account limits are the
  user's own responsibility;
- no commercial resale, bulk crawling, or CAPTCHA bypass;
- platform pages change; a source may break — report it via Issue.

---

## 📄 License

[MIT](LICENSE)
