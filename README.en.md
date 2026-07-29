# jobfindsme · AI Job Search Engine

> **5 platforms, one search · Local resume matching · Direct apply links**
>
> BOSS Zhipin · Liepin · 51job · Zhaopin · Lagou

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![latest](https://img.shields.io/badge/release-latest-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**jobfindsme** is a standard MCP Server that turns your AI agent into a job search engine. It searches 5 major Chinese recruitment platforms simultaneously, matches results against your local resume, and returns every job with a match score, evidence-based reasons, and a direct apply link.

- 🔍 **One search, 5 platforms** — BOSS Zhipin · Liepin · 51job · Zhaopin · Lagou
- 📄 **Local resume matching** — resume never leaves your machine
- 📊 **Evidence-based results** — match percentage + skill comparison + reasons
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
based on ~/Documents/resume.pdf.
```

No workspace IDs or plan IDs needed — Core handles everything.

### 4. Enable platform search (one-time)

```bash
jobfindsme setup              # Start the isolated local Chrome bridge
```

> All five sources use the local Chrome CDP bridge. BOSS Zhipin additionally requires account login; public pages on other platforms may still present verification.

## Sources

**5 platforms cover most Chinese companies' job listings.**

| Platform | Access prerequisite | Strength |
|----------|---------------------|----------|
| **BOSS Zhipin** | Browser bridge + login | Large volume, common salary data |
| **Liepin** | Browser bridge | Mid-senior roles, MNC positions |
| **51job** | Browser bridge | Broad coverage, traditional + IT |
| **Zhaopin** | Browser bridge | General recruitment |
| **Lagou** | Browser bridge | Internet-focused roles |

> No single source covers every position — some roles appear only on company career sites or internal referral channels. These 5 platforms together provide the widest reach.

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
Use jobfindsme, based on ~/Documents/resume.pdf,
to find AI Agent engineer jobs in Shanghai and Shenzhen, 25K+, experienced, full-time, 1-5 years.

# With resume, broad search
Use jobfindsme, based on ~/Documents/resume.pdf,
to find LLM application developer jobs in Hangzhou, campus recruitment.

# Without resume, quick browse
Use jobfindsme to search autonomous driving algorithm jobs in Beijing, 30K+, experienced.

# Without resume, find internships
Use jobfindsme to search AI product manager internships nationwide.

# View details / save
Use jobfindsme to show me the details of job #3.
Use jobfindsme to save jobs #1, #4, and #6.
```

> Every result includes: job description, match score, apply link, and evidence-based reasons. Match scores require a resume; search works either way.

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
