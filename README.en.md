# JobFindsMe

> **Tired of switching between job apps? Let jobs find you.**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Turn your AI agent into a job search engine.** One sentence searches Baidu, Tencent, ByteDance, Meituan, Didi, Bilibili, and BOSS Zhipin simultaneously — matches against your resume and explains why each job fits.

## Quick Start

**Fastest way: ask your agent to install it.**

Just say in ZCode / Codex / Claude Code:

```
Install JobFindsMe for me
```

The agent handles install, MCP config, and Skill setup automatically. Then start searching.

**Or manually:**

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
jobfindsme doctor
jobfindsme install zcode    # or codex / claude / qwen
```

Restart your agent and say:

```
Use JobFindsMe to find AI Engineer roles in Shanghai, based on my resume.
```

No workspace IDs or plan IDs needed — Core handles everything.

## Why Not Job Apps?

| | Job Apps | JobFindsMe |
|---|---|---|
| Coverage | One platform | **8 sources at once** |
| Resume | Uploaded | **Stays local** |
| Recommendations | Black box | **Evidence-based** |
| Model API | — | **Not required** |
| Data export | Rarely | **One-click** |

## Sources

**8 auto-connectors** pull jobs directly. **29 one-click links** for everything else.

| Source | Method | Coverage |
|--------|--------|----------|
| Baidu, Tencent | SSR / JSON-LD | All roles |
| ByteDance, Meituan, Didi, Bilibili | Playwright SPA | All roles |
| **BOSS Zhipin** | Chrome CDP bridge | **Thousands of companies** |
| Airbnb China | Greenhouse API | China-based roles |

Plus 29 direct links to Alibaba, Huawei, JD.com, NetEase, and more.

## How It Works

```
Your agent (ZCode / Codex / Claude Code)
      │
      ▼
  JobFindsMe MCP Server (local stdio)
      │
      ├── Baidu SSR ────────────→ Baidu jobs
      ├── Tencent JSON-LD ──────→ Tencent jobs
      ├── Playwright SPA ───────→ ByteDance/Meituan/Didi/Bilibili
      ├── Chrome CDP bridge ────→ BOSS Zhipin (1000s of companies)
      └── Greenhouse API ───────→ Global companies
      │
      ▼
  Deduplicate → Filter → Evidence match → Top 10 + reasons + links
```

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
- BOSS connector uses YOUR Chrome, YOUR login — zero credential exposure
- Two-phase deletion enforced by Core

## Disclaimer

JobFindsMe is a local tool that helps organize and match job information you already have access to. The user bears all consequences of use (including platform account restrictions). Commercial resale, mass scraping, and bypassing platform restrictions are prohibited.

## License

[MIT](LICENSE)
