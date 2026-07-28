# JobFindsMe

> **Tired of switching between job apps? Let jobs find you.**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![v0.2.0-rc.5](https://img.shields.io/badge/release-v0.2.0--rc.5-blue)](https://github.com/russeell/jobfindsme/releases)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Turn your AI agent into a job search engine.** Discover jobs from verified career sources, match them against a local resume, and return evidence plus official application links.

## Quick Start

**Fastest way: ask your agent to install it.**

Just say in ZCode / Codex / Claude Code:

```
Install JobFindsMe for me
```

The agent handles install, MCP config, and Skill setup automatically. Then start searching.

**Or manually:**

```bash
pip install "jobfindsme[browser] @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
jobfindsme doctor
jobfindsme install zcode    # or codex / claude / qwen
```

Restart your agent and say:

```
Use JobFindsMe to find AI Engineer roles in Shanghai, based on my resume.
```

No workspace IDs or plan IDs needed — Core handles everything.

Jobs use one stable format. Recruitment track and employment type are separate:

```text
1. AI Application Engineer｜Example Tech｜Shanghai｜社招｜正式｜匹配度 86%
   投递链接：https://careers.example.com/jobs/123

2. LLM Engineer Intern｜Example Tech｜Beijing｜校招｜实习｜匹配度 81%
   投递链接：https://careers.example.com/jobs/456
```

## Why Not Job Apps?

| | Job Apps | JobFindsMe |
|---|---|---|
| Coverage | One platform | **Multiple verifiable sources** |
| Resume | Uploaded | **Stays local** |
| Recommendations | Black box | **Evidence-based** |
| Model API | — | **Not required** |
| Data export | Rarely | **One-click** |

## Sources

Sources are classified as verified, beta, experimental, or link-only.

| Source | Method | Coverage |
|--------|--------|----------|
| Baidu | SSR | Verified |
| ByteDance, Meituan | Playwright SPA | Verified; browser extra required |
| Airbnb China | Greenhouse API | Contract and snapshot verified |
| Airwallex | Ashby API | Contract and China snapshot verified |
| Didi, Bilibili | Playwright SPA | Beta; query quality incomplete |
| BOSS Zhipin | Chrome CDP bridge | Experimental; explicit opt-in |
| Tencent and other sites | Direct links | Not described as auto-fetched |

Plus 29 direct links to Alibaba, Huawei, JD.com, NetEase, and more.

## How It Works

```
Your agent (ZCode / Codex / Claude Code)
      │
      ▼
  JobFindsMe MCP Server (local stdio)
      │
      ├── Baidu SSR ────────────→ Baidu jobs
      ├── Playwright SPA ───────→ ByteDance/Meituan
      ├── Greenhouse/Ashby ─────→ China roles at global companies
      ├── Beta connectors ──────→ Didi/Bilibili (opt-in)
      └── BOSS CDP bridge ──────→ Experimental (opt-in)
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
- The experimental BOSS connector only attaches to a local Chrome CDP session
- Two-phase deletion enforced by Core

## Disclaimer

JobFindsMe is a local tool that helps organize and match job information you already have access to. The user bears all consequences of use (including platform account restrictions). Commercial resale, mass scraping, and bypassing platform restrictions are prohibited.

## License

[MIT](LICENSE)
