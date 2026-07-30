# jobfindsme · Your AI Job Search Radar

> **Search multiple job platforms at once, match against your resume, and focus
> future searches on new opportunities.**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![latest](https://img.shields.io/badge/release-latest-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**jobfindsme** lets your AI agent search several job sources from one place,
remove duplicates, explain matches, and remember what you have already seen.

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

## Job Sources

| Platform | Current role | Access prerequisite |
|----------|---------------------|----------|
| **BOSS Zhipin** | Primary recommendation source | Login required |
| **Liepin** | Searchable; full details available for some jobs | Usually no login |
| **51job** | Searchable; some job fields may be incomplete | Usually no login |
| **Zhaopin** | Searchable; full details available for some jobs | Usually no login |
| **Lagou** | Experimental; verification may interrupt access | Depends on page state |

Source availability and job completeness vary. jobfindsme skips unavailable
sources, reports the limitation, and continues with the others. See
[PROJECT_SPEC.md](PROJECT_SPEC.md) for implementation and quality criteria.

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
