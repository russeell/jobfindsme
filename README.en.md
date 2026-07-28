# JobFindsMe

**Let the AI agent you already use discover, filter, and track jobs from 28+ official Chinese career sources — with your resume staying local.**

[![CI](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml/badge.svg)](https://github.com/russeell/jobfindsme/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-111111)](https://modelcontextprotocol.io/)
[![Release](https://img.shields.io/badge/release-v0.2.0--rc.4-blue)](https://github.com/russeell/jobfindsme/releases)
[![License](https://img.shields.io/github/license/russeell/jobfindsme)](LICENSE)

> Current version **v0.2.0-rc.4** — 3 auto-connectors, 28 direct search links, 143 automated tests, supports ZCode / Codex / Claude Code / Qwen Code.

JobFindsMe is a **local-first, agent-native** job discovery and tracking engine. It is not a job board, and it will never auto-apply. Deterministic resume parsing, job discovery, deduplication, filtering, evidence-based matching, and state management run in a local Core. Your existing AI agent handles understanding your intent and explaining results.

## One-liner

```
You: "Use JobFindsMe to find AI Engineer roles in Shanghai and Hangzhou,
      based on my resume at ~/Documents/resume.pdf, 0-3 years, 20-40K."

Agent + JobFindsMe:
  1. Parse resume locally → auto-confirm skill facts
  2. Pull jobs from Baidu/Tencent/Airbnb public APIs
  3. Hard filter → deduplicate → evidence match
  4. Return Top 10 + match reasons + apply links
  5. Also provide 28 one-click official search links
```

## 28+ Chinese Job Sources

### Auto-Discovery (Agent pulls directly, no manual work)

| Source | Method | Coverage |
|--------|--------|----------|
| **Baidu** | Public SSR page parsing | AI, LLM, Agent roles |
| **Tencent** | Schema.org JSON-LD | All job families |
| **Airbnb China** | Greenhouse public API | Including AI Engineer |

### One-Click Search Links (dynamically generated with your search terms)

| Category | Companies |
|----------|-----------|
| 🏢 Big Tech | ByteDance, Alibaba, Huawei, Meituan, JD.com, NetEase, Pinduoduo |
| 🔬 Notable | Xiaohongshu, Kuaishou, Xiaomi, Didi, Ctrip, Bilibili, Ant Group, Lenovo, DJI, NIO, SenseTime |
| 📋 Platforms | BOSS Zhipin, Liepin, Zhaopin, 51job |

## Why Not Job Apps?

| | Job Apps | JobFindsMe |
|---|---|---|
| Resume | Uploaded to platform | **Stays local** — only structured facts kept |
| Recommendations | Black-box algorithm | **Every match has evidence** |
| Cross-platform | Search each app separately | **One entry, 28 sources** |
| API Keys | Not applicable | No model API key needed for Core |
| Data portability | Usually unsupported | **One-click export**, safe deletion |

## Quick Start

```bash
python3 -m pip install \
  "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.4"
jobfindsme doctor
jobfindsme install zcode    # or: codex, claude, qwen
```

Restart your agent and say:

```
Use JobFindsMe to find AI Engineer roles in Shanghai.
```

No workspace IDs or plan IDs needed — Core resolves everything automatically.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `setup_profile` | Import resume, auto-confirm facts |
| `configure_search` | Set roles, cities, salary, experience |
| `search_jobs` | Discover and match jobs |
| `get_jobs` | Paginate job summaries |
| `get_job_details` | Read single job detail |
| `update_job_state` | Save / dismiss / mark applied |
| `configure_monitor` | Set up recurring checks |
| `export_local_data` | Export local records |
| `delete_local_data` | Two-phase safe deletion |

## Privacy

- Agent never reads the complete resume — only the local path is passed
- Only structured facts and minimum evidence are retained
- Job descriptions are treated as untrusted external content
- Deletion requires preview + short-lived confirmation token
- HTTP redirects are validated hop-by-hop

## Status

- ✅ 143 automated tests, Python 3.11 / 3.12 CI
- ✅ 4 Agent integrations (ZCode / Codex / Claude Code / Qwen Code)
- ✅ 3 auto-connectors + 28 direct search links
- 🔜 Chinese labeled benchmark (in progress)
- 🔜 Personal field trial report (in progress)

## License

[MIT](LICENSE)
