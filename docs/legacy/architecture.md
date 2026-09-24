> Compatibility documentation for the retained CLI/MCP. The current product is the [desktop app](../../README.md). Native plugin marketplace distribution was retired in D47. Historical platform claims below do not establish desktop source availability.

# Architecture

Agent Job Search is a **local-first job search and incremental tracking engine
for AI Agents** — a four-source (BOSS直聘 + 猎聘 + 智联招聘 + 前程无忧) MCP Server with local
SQLite persistence.

## Four user-facing concepts

Everything the user ever hears about reduces to four concepts:

| Concept | 中文 | Meaning | Owned by |
|---|---|---|---|
| Profile | 我是谁 | resume parsed into reviewable facts (skills, experience, education) | `profiles/service.py` |
| Search | 我找什么 | role, locations, salary, track, type — the current preferences | `search/orchestrator.py` |
| Job | 找到了什么 | a discovered posting with evidence, signals, and apply link | `search/tracking.py` |
| Tracking | 和上次相比有什么变化 | new / changed / reopened / closed, and applied-saved-rejected state | `tracking` (impressions, states) |

Internal concepts — `Workspace`, `ActiveContext`, `SearchPlan ID`,
`SourceSubscription`, `CanonicalJob`, `SourceRecord` — never appear in
user-facing docs or Agent conversation.

## Reading a search request in 30 minutes

A search request follows one fixed path:

```text
MCP Handler (mcp/tools.py)
  → SearchOrchestrator (core/search.py)
      → Connectors (connectors/boss_zhipin.py, connectors/pure_http.py)
      → Normalize / Deduplicate (importing/normalizer.py, importing/repository.py)
      → Filter / Rank (matching.py)
      → Tracking (tracking.py)
  → Presentation (presentation/search_result.py, presentation/job_block.py)
  → MCP Response (mcp/responses.py)
```

Where each decision happens:

- **过滤** — `matching.py::_hard_filter` (location, salary, track,
  type, exclusions, seniority, stale liveness)
- **排序** — `matching.py::_score_signals` (deterministic
  evidence score: hard constraints stay pass/fail/unknown; role, skill,
  experience, education, and liveness evidence produce a separate 0–100 score
  plus evidence coverage
  bonus from skill overlap, experience, degree, liveness, and salary
  visibility)
- **记录变化** — `search/tracking.py` (select_and_record: new, changed,
  reopened, closed, repeated suppression; applied jobs are never
  re-suggested)
- **返回 Agent** — `mcp/responses.py` (bounded structured facts in
  `structuredContent.jobs` + compact factual `summary`; the host Agent
  organizes the final user-facing expression)

## Layering

```text
CLI / MCP
    ↓
Application Core (app.py — thin facade)
    ↓
Domain Services (profiles, preferences, matching, importing, tracking)
    ↓
Storage / Connectors (storage.py, connectors/)
```

Dependency direction is one way. Core must not import MCP, an Agent SDK,
a hosted model provider, or a notification SDK. Adapters must not
duplicate matching rules.

### Product layering

The product is a **query layer** with an optional upper layer on top:

| Layer | What it is | Entry points |
|---|---|---|
| Core — query layer | discovery, normalization, cross-source dedup, hard filtering, deterministic ranking, source status, change detection | `search_jobs`, `get_jobs`, and `setup` as query configuration |
| Optional upper layer | resume profile, job state (saved / applied / rejected), incremental radar suppression | `setup` with `resume_path`, `update_job_state`, `search_jobs.include_seen` |

A caller that ignores the entire upper layer still has a complete query
surface. Positioning, README, and SKILL all describe the project in terms of
the core layer; the upper layer is documented as optional capability, never
as the product.

`search_jobs` also has two response modes. `response_mode: "summary"`
(default) adds a compact three-layer Chinese summary for conversational
hosts; `response_mode: "facts"` returns the same `structuredContent.jobs`
with no server-authored recommendations or next-step advice, so a
programmatic caller renders its own output. Both modes return byte-identical
structured facts.

## Agent distribution

```text
skills/agent-job-search/SKILL.md                 canonical behavior source
  └─ src/jobfindsme/resources/agent_job_search/  generated wheel mirror

.mcp.json                                 shared stdio MCP definition
```

One standard MCP config plus one Skill serves every MCP-compatible host.
The compatibility command `agent-job-search connect` installs the Skill and config.
`scripts/sync_skill.py --check` and distribution tests enforce the boundary.

Agent behavior has a separate gate from Python correctness. Fixed prompts and
normalized transcripts under `evaluation/agent_behavior/data/` test tool routing,
factual output (apply URLs preserved, no fabricated facts), direct links,
degraded-source handling, state updates, incremental search, and resume
privacy. Contract fixtures run in CI; live Codex/Claude/Cursor transcripts
are required for release compatibility claims.

## Modules

| Path | Role |
|---|---|
| `contracts/` | domain types, one file per domain, unified exports |
| `search/orchestrator.py` | search use case: preferences → refresh → match → radar |
| `profiles/` | resume extraction + parser + service |
| `search/matching.py` | hard filter, signal extraction, deterministic coarse rank |
| `importing/` | connectors output → normalized canonical jobs |
| `connectors/` | BOSS直聘、猎聘、智联招聘、前程无忧的来源适配器 |
| `search/tracking.py` | impressions (incremental radar) and user job state |
| `presentation/` | deterministic rendering of search results and job blocks |
| `mcp/` | protocol entry (server.py), contracts (schemas.py), tools (tools.py), responses (responses.py) |
| `installer.py` | compatibility installation for hosts without native plugins |
| `doctor.py` | local diagnostics |
| `evaluation/` | dev-time quality gates (datasets, metrics, regression, field trials) |
| `skills/` | canonical Agent behavior shared by native host adapters |
| `evaluation/agent_behavior/data/` | fixed prompts and cross-Agent behavior evidence |
| `cli.py` | CLI for setup, doctor, profile import, admin |

A complete engineering spec lives at `docs/internal/project_spec.md`.
