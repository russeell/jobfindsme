# JobFindsMe · AI Job Search Engine

> **5 platforms, one search · Local resume matching · Direct apply links**
>
> BOSS Zhipin · Liepin · 51job · Zhaopin · Lagou

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**JobFindsMe** is a standard MCP Server that turns your AI agent into a job search engine. It searches 5 major Chinese recruitment platforms simultaneously, matches results against your local resume, and returns every job with a match score, evidence-based reasons, and a direct apply link.

- 🔍 **One search, 5 platforms** — BOSS Zhipin · Liepin · 51job · Zhaopin · Lagou
- 📄 **Local resume matching** — resume never leaves your machine
- 📊 **Evidence-based results** — match percentage + skill comparison + reasons
- 🔗 **Direct apply links** — one click to the official job page
- 🔌 **Standard MCP** — works with any MCP-compatible agent

## Quick Start

### 1. Install

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
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
Use JobFindsMe to find AI Engineer roles in Shanghai and Shenzhen,
based on ~/Documents/resume.pdf.
```

No workspace IDs or plan IDs needed — Core handles everything.

### 4. Enable platform search (one-time)

```bash
jobfindsme setup              # Open Chrome with 4 login pages
```

> Liepin, 51job, Zhaopin, and Lagou work **without login**. Only BOSS Zhipin requires authentication.

## Sources

**5 platforms cover most Chinese companies' job listings.**

| Platform | Login | Jobs/query | Strength |
|----------|:-----:|:----------:|----------|
| **BOSS Zhipin** | Required | ~15 | Largest volume, plain-text salary |
| **Liepin** | ❌ | ~42 | Mid-senior roles, MNC positions |
| **51job** | ❌ | ~20 | Broad coverage, traditional + IT |
| **Zhaopin** | ❌ | ~15 | General recruitment |
| **Lagou** | ❌ | ~15 | Internet-focused |

> No single source covers every position — some roles appear only on company career sites or internal referral channels. These 5 platforms together provide the widest reach.

## Prompt Templates

**With resume (auto-parse + match):**

```
Use JobFindsMe to find [role] jobs in [city], based on [resume path].
```

**Without resume (search only, no scoring):**

```
Use JobFindsMe to search [role] jobs in [city].
```

**View job details:**

```
Use JobFindsMe to show me the details of job #3.
```

> Every result includes: job description, match score, apply link, and evidence-based reasons.

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
