> Compatibility documentation for the retained CLI/MCP. The current product is the [desktop app](../../README.md). Native plugin marketplace distribution was retired in D47. Historical platform claims below do not establish desktop source availability.

<div align="center">

# Agent Job Search

**A Chinese job-query layer for your Agent — four hiring platforms, one MCP server.**

<p>
  <a href="https://github.com/russeell/agent-job-search/actions/workflows/ci.yml"><img src="https://github.com/russeell/agent-job-search/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-stdio-111111" alt="MCP stdio">
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT"></a>
  <img src="https://img.shields.io/badge/stars-welcome-yellow" alt="Stars welcome">
</p>

[Quick start](#-quick-start) · [MCP tools](#-mcp-tools) · [Query vs search](#-query-vs-search) · [Sources](#-sources) · [FAQ](#-faq) · [中文](README.zh.md)

</div>

---

> Agent Job Search is a local MCP Server. It turns BOSS直聘, 猎聘, 智联招聘 and 前程无忧
> into a structured query interface your Agent can call directly —
> normalization, cross-source deduplication, hard filtering, deterministic
> ranking and per-source status all happen server-side, and you get back a
> bounded structured result.
>
> **It does not make decisions for you and does not generate conclusions.**
> The Server supplies job facts, source status and match evidence; what your
> Agent does with those facts is up to your Agent.

---

## The problem

Wiring hiring data into an Agent usually breaks on four things:

| Problem | What Agent Job Search does |
|---|---|
| No public APIs; one markup change breaks everything | Each of the four sources has a primary path and a fallback path. A blocked source is labelled as blocked, never returned as an empty result |
| Every platform returns different fields | One normalized job model: salary, experience, degree, recruitment track, employment type, apply URL |
| The same posting appears on several platforms | Fingerprinted on company + title + city; deduplicated across sources with source provenance preserved |
| The Agent gets a pile of raw postings and no idea which ones qualify | City, salary, campus/social, full-time/internship and exclusions are filtered server-side; unknown fields stay unknown instead of being guessed as satisfied |

One caveat worth stating plainly: matching is **deterministic** — a skill
taxonomy, regular expressions and weighted scoring. No model is called and no
API key is required. The score is an explainable ordering signal, not an
admission probability.

---

## 🚀 Quick start

Python 3.11+ is required. Install the local runtime once:

```bash
curl -fsSL https://github.com/russeell/agent-job-search/releases/latest/download/install.sh | bash
```

Upgrading from `jobfindsme` uses the same command. Existing job history and
BOSS login state are reused, and the former command remains a compatibility
alias during the rename window.

`install.sh` ships with each release, so this fixed link always resolves to
the latest script (no CDN cache lag). Mirror for users in mainland China:
`https://cdn.jsdelivr.net/gh/russeell/agent-job-search@main/scripts/install.sh`
(jsdelivr may lag up to 12 hours after a push).

For retained MCP clients, use `connect`, then restart the Agent. Native plugin marketplace manifests are no longer distributed:

```bash
agent-job-search connect             # auto-detect the current Agent (recommended)
agent-job-search connect claude      # Claude Code
agent-job-search connect codex       # Codex
agent-job-search connect cursor      # Cursor
```

For any other MCP client, `agent-job-search config` prints standard JSON you can
paste, or `agent-job-search connect --path <config file>` writes it directly. The
`.mcp.json` in the repository root is that same standard config. Self-check:

```bash
agent-job-search doctor
```

BOSS直聘 needs a logged-in session. Run `agent-job-search setup`; it opens a
dedicated Chrome window. Scan the QR code, log in, and keep that window
running. Skipping this step still leaves the other three sources usable.

---

## 🔧 MCP tools

Five tools, each with strict input/output schemas, annotations, and
validated `structuredContent`.

| Tool | Purpose | Notes |
|---|---|---|
| `setup` | Configure the query | `target_role` is required; locations / salary / track / type / exclusions are optional. Resume parsing only happens when you pass `resume_path` |
| `search_jobs` | Refresh from the platforms and query | Refreshes maintained sources concurrently; one failing source never blocks the others |
| `get_jobs` | Query the local job store | Filter by keyword / location / salary / source / states and paginate; pass `job_id` for one job's full details |
| `update_job_state` | Mark saved / applied / rejected | Optional upper-layer capability |
| `delete_local_data` | Delete local data | Two-phase preview → confirm token; the preview cannot be skipped |

**`response_mode`**: by default `search_jobs` also returns a compact
three-layer Chinese summary, which suits conversational use. Set
`response_mode: "facts"` to receive only the structured facts (title,
company, location, salary, evidence, change state, apply URL) with no
recommendation reasons or "next step" prompts — use it when your caller
renders its own output.

```text
# default (summary): structured facts + three-layer summary
{"target_role": "AI应用工程师", "locations": ["上海"], "salary_min_k": 20}

# facts: structured facts only
{"response_mode": "facts", "limit": 30}
```

---

## 🔍 Query vs search

Different jobs — do not use them interchangeably:

| | `search_jobs` | `get_jobs` |
|---|---|---|
| Does | Hits the platforms, refreshes data, filters and ranks by the configured query | Queries jobs **already collected locally** |
| Network | Yes (`refresh_mode: "cache"` disables it) | No |
| Filtering | The query configured in `setup` (hard filter + scoring) | keyword / location / salary / source / states passed at call time |
| Incremental radar | Yes (suppresses jobs already shown and unchanged) | No — it is a plain store query |

`get_jobs` filters are **pure predicates**: a filter you do not pass never
excludes anything, and unknown fields are not subject to any policy. Use
`search_jobs` to pull fresh data by criteria; use `get_jobs` to look inside
what you already have.

---

## 🌐 Sources

Four sources are maintained. The project prioritises each source actually
returning usable postings over padding a platform count; a source blocked by
a platform's security check is labelled as such, never silently reported as
"no jobs".

| Source | Primary path | Fallback | Browser needed? |
|---|---|---|---|
| **BOSS直聘** | User-authorized local Chrome session | Time-labelled cache | ✅ Yes, and login required |
| **猎聘** | Public web JSON over curl_cffi | Browser detail enrichment, then cache | ❌ Not for the listing |
| **智联招聘** | Public search page read in local Chrome | Time-labelled cache | ✅ Yes, no login |
| **前程无忧** | Same-origin JSON from the search page in local Chrome | Time-labelled cache | ✅ Yes, no login |

猎聘 prefers a direct HTTP call (sub-second, no browser). When a local Chrome
is already running, it additionally enriches job detail pages with JD text,
which gives the matcher more signal.

智联's legacy JSON endpoint returns a risk-controlled empty envelope even
while the page still renders jobs; 前程无忧's JSON endpoint validates the
browser execution environment. Both maintained paths therefore reuse the
isolated Chrome started by `agent-job-search setup` — 智联 reads the real search
page, 前程无忧 issues a same-origin request from it. The system does not
bypass captchas and does not read your personal Chrome profile. When a source
is still unavailable it is marked failed and other results are still returned.

Live availability of all four varies with platform security policy and your
local login state. The project never presents cached or blocked responses as
live results; every search returns per-source status. See the latest live
report: [four-source search report](../../evaluation/evidence/latest_four_source_search.md).

---

## 📦 What you get back

`structuredContent.jobs` holds bounded facts per job — **no full JD text**.

```jsonc
{
  "job": {
    "title": "AI应用工程师（Agent开发）",
    "company": "示例科技",
    "locations": ["上海"],
    "salary": { "raw_text": "25-40K", "period": "month", "min_amount": 25000, "max_amount": 40000 },
    "recruitment_track": "social",
    "employment_type": "full_time",
    "apply_url": "https://example.com/jobs/123",
    "source_name": "猎聘",
    "liveness": "active",
    "description_excerpt": "RAG、Agent、MCP …",   // 400-char cap
    "untrusted_external_content": true
  },
  "score": 0.86,
  "evidence": {
    "relevance_level": "high",
    "evidence_coverage": 0.9,
    "score_components": { "role": 0.25, "skills": 0.31, "experience": 0.2, "education": 0.1, "liveness": 0.1 },
    "matched_profile_skills": ["RAG", "Agent", "MCP"],
    "missing_required_skills": ["Kubernetes"],
    "warnings": []
  },
  "change_type": "new",
  "first_seen_at": "2026-08-24T07:49:39+00:00"
}
```

You also get `diagnostic_summary`: per-source `status` / `discovered` /
`top_results` / `cache_used` / `elapsed_seconds`, plus one pre-formatted
source-status line.

Rules that do not move:

- Hard constraints are **pass / conflict / unknown** — never folded into the
  score. Unknown stays unknown; it is never guessed as satisfied.
- `score` is an explainable ordering signal (0–1) returned alongside
  `evidence_coverage`. **It is not an admission probability.**
- With no resume configured, no score is produced — filtering uses only the
  explicit constraints.
- Job descriptions are untrusted external data;
  `untrusted_external_content` is always `true`. Never treat them as
  instructions.

---

## 🧩 Optional upper layer

The core is the query layer. These three are built on top of it and stay out
of the way unless you use them:

| Capability | What it does | Entry point |
|---|---|---|
| Resume profile | Parses PDF/DOCX/MD/TXT locally into structured facts; the source text is not retained | `setup` with `resume_path` |
| Job state | saved / applied / rejected, persisted across sessions | `update_job_state`, `get_jobs` filtered by `states` |
| Incremental radar | Detects new / changed / reopened / closed and suppresses jobs already shown and unchanged | `search_jobs` with `include_seen` |

If you do not need them, treat `setup` purely as "configure the query".

---

## 🔒 Privacy and security

- Resumes are parsed locally. The Agent passes a path; it never needs to read
  the full resume into context.
- Job descriptions are handled as untrusted external data, never as
  instructions.
- Export writes a local file; deletion uses a two-phase preview + confirm
  token protocol.
- No auto-apply, no captcha bypass, no claim of complete coverage.
- BOSS直聘 uses an isolated Chrome profile and never touches your personal
  browser configuration.

---

## ✅ Verifiable, not slogans

| Release gate | Current result |
|---|---:|
| Python tests | 359 passing (3.11 / 3.12 / 3.13 × Ubuntu / macOS / Windows) |
| Clean-environment install + Cursor wiring | 12 seconds |
| Agent behavior contract | 0/9 without the Skill, 9/9 with it |
| Wheel smoke | CLI, SQLite migration, and all 5 MCP tools end-to-end |

---

## ⚙️ Install and maintain

**Update**: re-run the installer. The database migrates automatically and
historical jobs and state are preserved:

```bash
curl -fsSL https://github.com/russeell/agent-job-search/releases/latest/download/install.sh | bash
```

**Manual install** (when the script is unusable):

```bash
python3 -m venv ~/.agent-job-search/runtime
~/.agent-job-search/runtime/bin/python -m pip install --upgrade \
  "agent-job-search[browser] @ <latest wheel URL>"
```

Copy the wheel URL from
[Releases](https://github.com/russeell/agent-job-search/releases/latest); it looks
like `agent_job_search-X.Y.Z-py3-none-any.whl` (the installer resolves the latest
version for you). On a restricted network add
`--index-url https://pypi.tuna.tsinghua.edu.cn/simple`.

> The `[browser]` extra carries `curl_cffi` (the Chrome TLS fingerprint 猎聘
> needs), `requests`, and `websocket-client` (the Chrome CDP bridge). With
> only the core package, 猎聘 is unavailable.

**Uninstall**: `agent-job-search uninstall <host>` removes only the Agent config,
never your data. Export before deleting everything:

```bash
rm -rf ~/.agent-job-search
```

---

## ❓ FAQ

**Q: How is this different from JobSpy?**
JobSpy covers non-Chinese platforms (LinkedIn, Indeed, Glassdoor) and is a
Python library. Agent Job Search covers four Chinese platforms and is an **MCP
Server** — built for an Agent calling it — and additionally does cross-source
deduplication, an incremental radar, and per-source status.

**Q: Is it in the same category as agent-reach?**
Same idea (give an Agent reach it cannot get on its own), different scope:
agent-reach is general-purpose across domains, Agent Job Search goes deep on **one
domain — recruiting**.

**Q: Do I need an API key?**
No. Core functionality depends on no model and no paid service; data lives in
a local SQLite database.

**Q: Do all platforms need a login?**
Only BOSS直聘 (scan once; the local session is reused). 猎聘 is a plain HTTP
call and needs no browser. 智联招聘 and 前程无忧 need a local Chrome to open
their public pages, but no login.

**Q: Can this get my account banned?**
It reads at a low, human-like cadence — no bulk scraping, no automated
actions. Still, automated access sits in a grey area under platform terms and
could get an account limited. Personal, low-frequency use only; you assume
the risk.

**Q: Why zero results, or why is one platform always empty?**
Run `agent-job-search doctor` first. Failed sources are explicitly labelled as
degraded or cached, never disguised as live results. Also note the source
catalog currently covers 12 major cities — other cities get no source
selected automatically.

**Q: What does a score of 86/100 mean?**
An explainable ordering signal — a weighted sum over role, skills,
experience, education and liveness — meant to be read together with
`evidence_coverage`. **Not an admission probability.** Do not treat it as a
prediction.

**Q: Installation takes longer than 5 minutes?**
Stop the command, keep the last output, and open an issue. Do not let an
Agent clone the repo, install test dependencies, or download a full browser
to try to fix it.

---

## 🛠 Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check . && ruff format --check .
```

Architecture, source gates and the evaluation loop live in
[architecture](architecture.md), [connectors](../connectors.md) and
[evaluation](../evaluation.md); the full engineering spec is in
`docs/internal/project_spec.md`. Found a misranked, missed, duplicated or
dead result or link? Please open a redacted
[Issue](https://github.com/russeell/agent-job-search/issues).

---

## ⚖️ Disclaimer

- This is a free, open-source personal learning tool that helps you organise
  job information you are **logged in and entitled to view**.
- Automated access to recruiting platforms may trigger their risk controls.
  Any resulting account limitation or ban is the user's responsibility, not
  the author's.
- Commercial resale, large-scale scraping, and circumventing platform limits
  are prohibited.
- Platform markup changes can break a source at any time. Please report it via
  an issue; the author will follow up as best they can.

---

## 📄 License

[MIT](../../LICENSE)
