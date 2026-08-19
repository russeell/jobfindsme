# Architecture

jobfindsme is a **local-first job search and incremental tracking engine
for AI Agents** — a four-source (BOSS直聘 + 猎聘 + 智联招聘 + 前程无忧) MCP Server with local
SQLite persistence.

## Four user-facing concepts

Everything the user ever hears about reduces to four concepts:

| Concept | 中文 | Meaning | Owned by |
|---|---|---|---|
| Profile | 我是谁 | resume parsed into reviewable facts (skills, experience, education) | `core/profile_service.py` |
| Search | 我找什么 | roles, locations, salary, track, type — the active plan | `core/search.py` |
| Job | 找到了什么 | a discovered posting with evidence, signals, and apply link | `core/job_service.py` |
| Tracking | 和上次相比有什么变化 | new / changed / reopened / closed, and applied-saved-rejected state | `tracking` (impressions, states) |

Internal concepts — `Workspace`, `ActiveContext`, `SearchPlan ID`,
`SourceSubscription`, `CanonicalJob`, `SourceRecord` — never appear in
user-facing docs or Agent conversation.

## Reading a search request in 30 minutes

A search request follows one fixed path:

```text
MCP Handler (mcp/handlers/search.py)
  → SearchOrchestrator (core/search.py)
      → Connectors (connectors/boss_zhipin.py, connectors/pure_http.py)
      → Normalize / Deduplicate (importing/normalizer.py, importing/repository.py)
      → Filter / Rank (matching/ranker.py)
      → Tracking (job_impressions.py)
  → Presentation (presentation/search_result.py, presentation/job_block.py)
  → MCP Response (mcp/responses.py)
```

Where each decision happens:

- **过滤** — `matching/ranker.py::_hard_filter` (location, salary, track,
  type, exclusions, seniority, stale liveness)
- **排序** — `matching/ranker.py::_score_signals` (deterministic
  signal-match score: 60% hard-condition floor + up to 40% evidence
  bonus from skill overlap, experience, degree, liveness, and salary
  visibility)
- **记录变化** — `job_impressions.py` (select_and_record: new, changed,
  reopened, closed, repeated suppression; applied jobs are never
  re-suggested)
- **返回 Agent** — `mcp/responses.py` (bounded structured facts in
  `structuredContent.jobs` + compact factual `summary`; the host Agent
  organizes the final user-facing expression)

## Layering

```text
CLI / MCP
    ↓
Application Core (core/app.py — thin facade + use cases)
    ↓
Domain Services (profiles, search_plans, matching, importing, tracking)
    ↓
Storage / Connectors (storage.py, connectors/)
```

Dependency direction is one way. Core must not import MCP, an Agent SDK,
a hosted model provider, or a notification SDK. Adapters must not
duplicate matching rules.

## Agent distribution

```text
skills/jobfindsme/SKILL.md                 canonical behavior source
  └─ src/jobfindsme/resources/jobfindsme/  generated wheel mirror

.mcp.json                                 shared stdio MCP definition
.codex-plugin/plugin.json                 Codex plugin marketplace manifest
.claude-plugin/marketplace.json
  + .claude-plugin/plugin.json            Claude Code plugin marketplace manifest
.agents/plugins/marketplace.json          Agents SDK plugin marketplace manifest
.cursor-plugin/plugin.json                Cursor plugin manifest
```

One standard MCP config plus one Skill serves every MCP-compatible host.
Native plugin marketplaces (Codex / Claude Code) install the Skill and the
MCP config in a single command; `jobfindsme connect` covers every other host.
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
| `core/` | application layer: facade + four use cases |
| `profiles/` | resume extraction + parser + service |
| `matching/` | hard filter, signal extraction, deterministic coarse rank |
| `importing/` | connectors output → normalized canonical jobs |
| `connectors/` | BOSS直聘、猎聘、智联招聘、前程无忧的来源适配器 |
| `job_impressions.py`, `job_states.py` | impressions (incremental radar) and user job state |
| `presentation/` | deterministic rendering of search results and job blocks |
| `mcp/` | protocol entry, registry, handlers, responses |
| `installer/` | compatibility installation for hosts without native plugins |
| `evaluation/` | dev-time quality gates (datasets, metrics, regression, field trials) |
| `skills/` | canonical Agent behavior shared by native host adapters |
| `evaluation/agent_behavior/data/` | fixed prompts and cross-Agent behavior evidence |
| `cli.py` | CLI for setup, doctor, profile import, admin |

A complete engineering spec lives at `docs/internal/project_spec.md`.
