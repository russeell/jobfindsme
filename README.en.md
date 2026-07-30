# jobfindsme · Your Local Job Radar

> **Let your AI agent keep looking for jobs: discover across sources, focus on
> what is new, and remember every decision locally.**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![latest](https://img.shields.io/badge/release-latest-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**jobfindsme** is a local-first job radar exposed as a standard MCP Server.
It keeps your profile, search plans, job versions, and application state on
your machine. The first search establishes a baseline; repeated searches are
being evolved to focus on new and changed opportunities instead of returning
the same list again.

- 🔍 **Multi-source discovery** — connectors for BOSS Zhipin, Liepin, 51job, Zhaopin, and Lagou
- 📄 **Local resume matching** — resume never leaves your machine
- 📊 **Evidence-based results** — match percentage + skill comparison + reasons
- 🧠 **Persistent state** — remember saved, dismissed, and applied jobs across agents
- 🆕 **Incremental radar** — track new, changed, reopened, and closed jobs
- 🔗 **Direct job links** — one click to the source platform's job page
- 🔌 **Standard MCP** — works with any MCP-compatible agent

## Quick Start

### 1. Install

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@main"
```

### 2. Configure MCP

**Option A: print the JSON and paste it (any agent)**

```bash
jobfindsme config
```

Paste the output into any MCP-compatible agent's config file. Or write directly:

```bash
jobfindsme install --path ~/.your-agent/mcp.json
```

**Option B: shortcut for known agents**

```bash
jobfindsme install zcode     # ZCode
jobfindsme install claude    # Claude Code
jobfindsme install codex     # Codex
```

### 3. Restart your agent and search

```
Use jobfindsme to find AI Engineer roles in Shanghai and Shenzhen,
based on my local resume at ~/Documents/resume.pdf.
```

No workspace IDs or plan IDs needed — Core handles everything.

### 4. Enable platform search (one-time)

```bash
jobfindsme setup              # Start the isolated local Chrome bridge
```

> All five sources use the local Chrome CDP bridge. BOSS Zhipin additionally requires account login; public pages on other platforms may still present verification.

## Product Goals

1. Find more *qualified unique jobs*, not merely more raw records.
2. Save time by removing app switching and repeated reading.
3. Produce relevant recommendations with inspectable evidence.

## Source Maturity

| Platform | Current role | Access prerequisite |
|----------|---------------------|----------|
| **BOSS Zhipin** | Primary verified recommendation source | Browser bridge + login |
| **Liepin** | Discovery; detail enrichment pending | Browser bridge |
| **51job** | Discovery; detail enrichment pending | Browser bridge |
| **Zhaopin** | Discovery; parser quality under evaluation | Browser bridge |
| **Lagou** | Experimental; verification may block access | Browser bridge |

Connecting a source does not mean it already provides equal recommendation
quality. Live Loop reports measure latency, field completeness, valid links,
and human relevance before a source is described as verified.

The current five platform connectors still use the local browser bridge. The
target source architecture is hybrid:

```text
structured API / ATS → public HTTP → authenticated browser request
→ DOM extraction → local import
```

The browser remains appropriate for sources such as BOSS Zhipin that require a
user-owned login session. A verified public JSON or ATS endpoint should use a
lightweight HTTP connector instead of opening browser pages.

## Prompt Templates

**Full template (`[]` = optional, remove lines you don't need):**

```
Use jobfindsme,
based on [resume path]                  ← include only if you have a resume
to find [role] jobs in [cities]        ← required
salary [min]K-[max]K or [amount]+      ← optional
[campus / experienced]                  ← optional
[internship / full-time]                ← optional
[0-3 / 3-5 / …] years experience       ← optional
exclude [keywords]                      ← optional
```

**Examples:**

```bash
# With resume, precise search
Use jobfindsme, based on my local resume at ~/Documents/resume.pdf,
to find AI Agent engineer jobs in Shanghai and Shenzhen, 25K+, experienced, full-time, 1-5 years.

# With resume, broad search
Use jobfindsme, based on my local resume at ~/Documents/resume.pdf,
to find LLM application developer jobs in Hangzhou, campus recruitment.

# Without resume, quick browse
Use jobfindsme to search autonomous driving algorithm jobs in Beijing, 30K+, experienced.

# Without resume, find internships
Use jobfindsme to search AI product manager internships nationwide.

# View details / save
Use jobfindsme to show me the details of job #3.
Use jobfindsme to save jobs #1, #4, and #6.
```

> Results include a ranking score, direct link, and evidence-based reasons when
> the source provides sufficient fields. The score is not a hiring probability.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `setup_profile` | Import resume |
| `configure_search` | Set roles, cities, salary |
| `search_jobs` | Discover + match |
| `get_jobs` | Paginate results |
| `get_job_details` | Single job detail |
| `update_job_state` | Save/dismiss/applied |
| `configure_monitor` | Recurring checks |
| `export_local_data` | Export |
| `delete_local_data` | Two-phase deletion |

## Privacy

- Resume stays local — agent never reads the full file
- Only structured facts and minimum evidence retained
- CDP connectors only attach to a local Chrome DevTools session
- Two-phase deletion enforced by Core

## License

[MIT](LICENSE)
