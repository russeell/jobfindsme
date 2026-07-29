# jobfindsme Product And Architecture Specification

> Status: v0.2 active development
>
> Baseline: Agent-native, Local-first, MCP-standard
>
> Updated: 2026-07-29

## 1. Product Goal

jobfindsme 面向技术求职者和 AI 工具用户。提供本地简历或描述求职目标，
由 AI Agent 调用 jobfindsme，从五大招聘平台同步搜索、匹配和跟踪岗位。

一句话定位：

> 本地优先的 AI 求职引擎 — 五大平台一站式搜索，简历本地匹配，投递直达。

## 2. V0.2 Scope

V0.2 provides:

- local Workspace with accepted candidate profile;
- multiple Search Plans sharing profile facts;
- local resume parsing (auto-confirm fast path or paginated review);
- **5 CDP platform connectors** (BOSS直聘 · 猎聘 · 前程无忧 · 智联 · 拉勾);
- normalization, versioning, deduplication, freshness, and liveness checks;
- deterministic hard filters, BM25 ranking, match evidence, and **score threshold** (min 10%);
- job states (saved / applied / rejected) and feedback history;
- CLI, local stdio MCP Server, and **generic MCP install** (`jobfindsme config`);
- `AGENTS.md` — framework-agnostic Agent instructions for all MCP hosts;
- installer, upgrade, uninstall, doctor (with BOSS login check), and self-update;
- reproducible offline evaluation;
- optional local monitoring and Feishu summaries;
- zero-ID first use with automatic Workspace and Search Plan;
- prompt templates covering all search dimensions.

V0.2 explicitly excludes:

- Playwright SPA, SSR/JSON-LD, Greenhouse, Ashby, and Lever connectors (removed — redundant with platforms);
- a public Web application, accounts, cloud database, or multi-tenancy;
- automatic applications or bypassing login and anti-bot controls;
- a custom agent runtime;
- mandatory model APIs, vector databases, Redis, or hosted queues.

## 3. Product Principles

1. Job truth and liveness come before match scores.
2. Agent handles understanding and interaction; Core handles facts, state, and execution.
3. Every adapter calls the same Core and contains no business rules.
4. No API key means the complete deterministic workflow still works.
5. Resume content stays local and is minimized after parsing.
6. The four non-BOSS platforms work **without login** — only BOSS直聘 requires one-time setup.
7. Security cannot depend on a host agent or MCP client's optional behavior.

## 4. Main User Flow

```text
Install → jobfindsme config → paste JSON → restart agent
         (or: agent reads INSTALL.md and auto-installs)

First use:
  → agent asks: "登录过 BOSS直聘吗？" (AGENTS.md §First-Time Setup)
  → if no: jobfindsme setup → scan QR → done once

Search:
  → agent passes resume path to setup_profile
  → configure_search with roles, cities, salary, etc.
  → search_jobs across 5 platforms
  → results with match%, evidence, apply links
  → user saves / dismisses / marks applied

Results below 10% match are automatically filtered.
```

## 5. Architecture

```text
Any MCP Agent (Claude Code / Codex / ZCode / Hermes / …)
        │
        ▼
    AGENTS.md (read once, universal instructions)
        │
        ▼
  jobfindsme MCP Server (local stdio)
        │
        ├── BOSS直聘 CDP ────── 15+ jobs/query (requires login)
        ├── 猎聘 CDP ────────── 42+ jobs/query (no login)
        ├── 前程无忧 CDP ─────── 20+ jobs/query (no login)
        ├── 智联招聘 CDP ─────── 15+ jobs/query (no login)
        └── 拉勾 CDP ────────── 15+ jobs/query (no login)
        │
        ▼
    Deduplicate → Filter (≥10%) → BM25 Rank → Evidence → Top N + reasons + links
```

Core must not import FastAPI, MCP SDKs, agent SDKs, or UI packages.

## 6. Local Data Model

```text
Workspace
|- CandidateProfile
|  |- SourceDocument
|  `- ProfileFacts
|- SearchPlan A / B …
|- Jobs and JobVersions
|- MatchEvidence
|- FeedbackEvents and JobState
`- MonitorRuns and JobStateEvents
```

Profile facts are shared across plans. Role, location, salary, experience,
and exclusions belong to a Search Plan.

## 7. Resume Privacy

The agent must not read the complete resume. Pass only the file path to
`setup_profile`. Import modes: `reference`, `managed`, `forget-source`.
Default auto-confirms facts for immediate first search.

## 8. Destructive Operation Safety

Two-phase deletion: `preview` → `confirm` with short-lived single-use token.

## 9. MCP Surface

```text
setup_profile       — import and parse resume
configure_search    — set roles, cities, salary, exclusions
search_jobs         — discover across 5 platforms + match
get_jobs            — pagination and state filtering
get_job_details     — single job detail (untrusted external content)
update_job_state    — save / applied / rejected
configure_monitor   — recurring scheduled checks
export_local_data   — local export (path + hash + counts only)
delete_local_data   — two-phase deletion
```

`workspace_id` and `plan_id` are optional adapter escape hatches — Core resolves
the active context automatically.

## 10. Source Strategy

### 10.1 五个平台，覆盖主流渠道

| 平台 | 登录 | 每次岗位 | 特点 |
|------|:--:|:--:|------|
| BOSS直聘 | 需要 | ~15 | 岗位最多，明文薪资 |
| 猎聘 | ❌ | ~42 | 中高端 + 外企中国岗 |
| 前程无忧 | ❌ | ~20 | 传统行业 + IT，覆盖面广 |
| 智联招聘 | ❌ | ~15 | 综合招聘 |
| 拉勾 | ❌ | ~15 | 互联网专注 |

腾讯、阿里、字节、拼多多、小米、网易、美团……绝大部分公司的岗位
都在这五个平台上发布。不保证覆盖所有公司所有岗位。

### 10.2 技术方案

全部通过 Chrome CDP 实现：
- **BOSS直聘**：注入 XHR 调用内部搜索 API（明文薪资）
- **猎聘 / 前程无忧 / 智联 / 拉勾**：导航搜索页 → JS DOM 提取

用户运行 `jobfindsme setup` 一次，在隔离 Chrome profile 中登录 BOSS。
其他四个平台无需登录即可搜索。登录态本地持久保存。

### 10.3 删掉的 Connector

以下 Connector 已从默认源移除（冗余或零产出）：

| Connector | 原因 |
|-----------|------|
| Playwright SPA (字节/美团/滴滴/B站) | 岗位已在五大平台上 |
| BaiduCareer (SSR) | 同上 |
| Greenhouse (Airbnb) | 0 条中国 AI 岗 |
| Ashby (Airwallex) | 数据解析 bug，0 条 |
| Lever | API 大面积关闭 |
| JsonLdCareerSite | 未被任何源使用 |

代码保留 `JSON_FILE` 和 `CSV_FILE` 用于用户自导入。

### 10.4 Agent Compatibility

jobfindsme 是标准 MCP Server。适配所有 MCP 兼容的 Agent：

```text
安装方式：
  jobfindsme config           → 输出标准 JSON → 粘贴到任意 Agent 配置
  jobfindsme install --path   → 直接写入自定义配置路径
  jobfindsme install <name>   → 快捷安装（claude / codex / zcode / …）
```

`AGENTS.md` 提供框架无关的调用说明，所有 Agent 首次读取后即可使用。

## 11. Output Format

每条岗位必须包含四项：

1. 岗位介绍 — title, company, location, salary, track, type
2. 匹配度 — 🎯 percentage
3. 投递链接 — 🔗 official URL
4. 推荐理由 — evidence-based (reasons + warnings)

低于 10% 匹配的结果自动过滤。按分数降序，最多 15 条。

## 12. Delivery Milestones

1. ✅ Product and architecture baseline.
2. ✅ Local Workspace, Search Plans, and resume lifecycle.
3. ✅ Deterministic matching, offline evaluation.
4. ✅ Product-grade CLI and local stdio MCP Server.
5. ✅ Generic MCP install + AGENTS.md for all agents.
6. ✅ One-command install, upgrade, uninstall, doctor, self-update.
7. ✅ Score threshold filtering (≥10%).
8. ✅ 5 CDP platform connectors (BOSS / Liepin / 51job / Zhaopin / Lagou).
9. ✅ Prompt templates with full field coverage.
10. ✅ BOSS login tutorial with screenshot.
11. ✅ CI pipeline (ruff + pytest + smoke test).
12. □ Personal field trial with logged-in BOSS session.
13. □ Labeled benchmark (50+ jobs across multiple days).
14. □ Monitor + Feishu notifications in production.
15. □ Release hardening and PyPI publication.
