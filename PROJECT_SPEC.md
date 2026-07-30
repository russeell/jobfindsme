# JobFindsMe Product and Engineering Specification

## 1. Product Goal

JobFindsMe is a local-first job discovery and tracking engine for AI Agents.
It helps a user find more qualified jobs with less repeated work:

```text
local resume + natural-language constraints
→ multi-source discovery
→ normalization and deduplication
→ hard filters and evidence-based ranking
→ direct apply links
→ later searches report only useful changes
```

The product is successful when users discover previously unseen, relevant,
valid jobs faster. Connector count and raw crawl count are not product goals.

## 2. Scope

### In scope

- local resume parsing and confirmed profile facts;
- reusable search plans;
- job discovery from maintained sources and user imports;
- deterministic filtering, ranking, evidence, and gap explanation;
- canonical jobs, source provenance, liveness, and version history;
- seen, saved, dismissed, and applied state;
- incremental search, monitoring, and Feishu notification;
- CLI, local stdio MCP, Agent Skills, diagnostics, and export/delete;
- reproducible evaluation and bad-case regression.

### Out of scope

- automatic application or recruiter messaging;
- CAPTCHA bypass, signature cracking, or high-volume crawling;
- hiring probability prediction;
- public SaaS storage of resumes;
- claims of complete job-market coverage.

## 3. User Experience

First use should require a resume path and one request:

```text
Use jobfindsme with ~/Documents/resume.pdf.
Find full-time experienced AI application roles in Shanghai and Hangzhou,
20K+ monthly salary.
```

Core imports the resume locally, derives a reviewable plan, searches, and
returns qualified jobs. The user must not manage Workspace IDs, Plan IDs,
Connector kinds, or CDP ports.

Later use should be one sentence:

```text
Continue finding new jobs.
```

The response prioritizes new, changed, reopened, and closed jobs. Unchanged seen
jobs are suppressed unless requested.

Every recommendation must include:

1. title, company, location, salary, recruitment track, and employment type;
2. ranking score and evidence confidence;
3. resume/JD evidence supporting the recommendation;
4. gaps and unknown required fields;
5. novelty or user state;
6. one direct source link.

Scores are deterministic ranking scores, never hiring probabilities.

## 4. Architecture

```text
Agent hosts
  └── stdio MCP adapter
        └── Core API
              ├── Profile and Search Plan
              ├── Source Scheduler
              │     ├── structured HTTP connector
              │     ├── browser connector
              │     └── file import
              ├── Normalization and Canonical Job
              ├── Filtering and Matching
              ├── Incremental Radar
              └── Monitoring and Notifications
                    └── SQLite
```

Dependency direction is inward:

```text
CLI / MCP / scheduler → Core → domain services → storage and connector ports
```

Core must not import MCP, FastAPI, an Agent SDK, or a hosted model provider.
Agent hosts are adapters, not separate product implementations.

## 5. Core Contracts

Typed contracts define module boundaries:

- `CandidateProfile` and confirmed `ProfileFact`;
- `SearchPlan`;
- `DiscoverySource` and `SourceRunStats`;
- `RawJobRecord`, `JobPosting`, `CanonicalJob`, and `JobSourceRecord`;
- `JobMatch`, `MatchEvidence`, and `JobSummary`;
- `SearchRunDiagnostics`;
- `ToolResult` and structured tool errors.

Raw source payloads are immutable evidence. Normalized fields may change without
destroying provenance. External descriptions are always marked untrusted.

SQLite stores workspaces, active context, profiles, plans, source subscriptions,
jobs, source records, impressions, state events, monitor runs, and migrations.
Historical records from retired sources remain readable.

## 6. Source Strategy

### 6.1 Current maintained sources

| Source | Current transport | Quality role |
|---|---|---|
| BOSS Zhipin | user-authorized local CDP | primary live recommendation source |
| Liepin | CDP list and bounded details | candidate discovery |
| Zhaopin | CDP list and bounded details | candidate discovery |
| 51job | CDP list | candidate discovery |

Lagou is retired from live discovery. Frequent interactive verification,
incomplete fields, and added latency did not justify its observed contribution.
The legacy source kind remains readable only for old workspaces and records.

### 6.2 Target strategy

Each source uses the lowest-cost verified transport:

```text
verified structured HTTP
→ browser using a user-authorized session when required
→ recent successful cache marked with age and degraded state
→ explicit failure
```

HTTP is not automatically better. A proposed HTTP connector must prove that its
endpoint is stable enough for personal low-frequency use and does not depend on
committed secrets, reverse-engineered signatures, CAPTCHA bypass, or hidden
credential export.

Browser access is bounded:

- one dedicated local Chrome profile;
- background targets are closed after each operation;
- source calls have timeouts and run independently;
- one failed source cannot fail the whole search;
- list discovery and detail enrichment have separate budgets;
- absent jobs from partial browser pages cannot be marked closed.

### 6.3 Source promotion gate

A new transport or source is not enabled by default until it has:

1. sanitized recorded fixtures and schema-contract tests;
2. valid direct links and provenance;
3. measured P50/P95 latency and timeout behavior;
4. field-completeness comparison against the current implementation;
5. partial-failure and stale-cache tests;
6. at least three independent live runs;
7. human labels showing useful Top-K contribution;
8. a documented access and maintenance boundary.

Candidate HTTP implementations for Liepin, Zhaopin, and 51job should be tested
behind this gate. They are not advertised before passing it.

### 6.4 Search modes

| Mode | Remote work | Purpose |
|---|---|---|
| `fast` | refresh primary live source; reuse other fresh caches | interactive use |
| `cache` | no remote access | compare and inspect existing jobs |
| `full` | refresh all maintained sources in parallel | monitoring and evaluation |

All outputs expose source status, elapsed time, cache age, and degraded state.

## 7. Matching and Incremental Radar

Hard filters run before ranking:

- target role family;
- location;
- salary when reliably normalized;
- experience when known;
- campus/social and internship/full-time;
- user exclusions.

Unknown data is reported, not invented. Remaining jobs are ranked with title
signals, BM25-style text relevance, confirmed profile skills, and evidence
coverage. Cross-source records are merged into a canonical job while preserving
every source link.

Search records impressions. The next run compares canonical identity, content
hash, liveness, and user state to classify:

- new;
- materially changed;
- reopened;
- closed;
- unchanged and already seen.

## 8. Adapters and Installation

The release artifact is one Python wheel. Every Agent uses the same isolated
runtime:

```text
install wheel once
→ jobfindsme connect <agent>
→ restart Agent
```

`connect` is idempotent and only adapts the MCP config path and Skill location.
WorkBuddy is not a separate installation. Known hosts include Codex, Claude,
Qwen, Kimi, TRAE, ZCode, Qoder, and WorkBuddy. Unknown MCP clients use the
standard JSON emitted by `jobfindsme config`.

Release CI must install the wheel in a clean environment, initialize SQLite,
configure WorkBuddy as a representative JSON host, list MCP tools, and stay
under the installation time budget.

## 9. Privacy and Safety

- Core receives a resume file path and parses locally.
- Default import keeps structured facts and minimal evidence, not a copied PDF.
- Job descriptions never become Agent instructions.
- Export writes a local file and returns only path, hash, and counts.
- Delete requires preview plus a short-lived, single-use confirmation token.
- Data directories are private and database files are not shared.
- No automatic applications, recruiter messages, CAPTCHA bypass, or bulk crawl.

## 10. Evaluation Loop

Evaluation is a fast funnel, not a fixed seven-day wait:

| Level | Time | Purpose |
|---|---:|---|
| L0 | 1-2 min | unit, contract, migration, lint |
| L1 | 2-5 min | deterministic snapshot replay |
| L2 | 5-15 min | one live source smoke |
| L3 | 15-30 min | baseline/candidate human pairwise comparison |
| L4 | same day | incremental new/changed/closed verification |
| L5 | release gate | 3 live runs and at least 50 human labels |
| L6 | optional | multi-day operational soak |

Primary product metrics:

- qualified unique jobs and source contribution;
- Precision@10 and NDCG@10;
- valid direct-link rate;
- duplicate leakage;
- hard-filter false-negative rate;
- first qualified result and end-to-end latency;
- source success, timeout, zero-result, and cache-fallback rates;
- new useful jobs found on later runs.

Every production-affecting change follows:

```text
baseline → candidate → same fixtures → live smoke → human comparison
→ keep only if product metrics improve without unacceptable regression
```

Synthetic datasets are regression fixtures and cannot support public quality
claims. Bad cases become labeled examples and regression tests.

## 11. Definition of Done

A feature is complete only when:

- typed contracts and failure behavior are defined;
- unit and integration tests pass;
- installed-wheel smoke passes;
- source and privacy boundaries remain intact;
- diagnostics and evidence distinguish observed facts from assumptions;
- user-facing and engineering documentation agree;
- claimed metrics are generated by committed evaluation code.

## 12. Engineering References

Design decisions should inspect primary code and authoritative documentation
before implementation:

- [mergedao/mcp-jobs](https://github.com/mergedao/mcp-jobs): simple MCP
  onboarding and browser-based multi-source extraction; useful for UX, but its
  browser-first implementation does not prove a source has a stable HTTP API.
- [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy): independent
  source scrapers, normalized output, retries, and parallel source execution.
- [can4hou6joeng4/boss-agent-cli](https://github.com/can4hou6joeng4/boss-agent-cli):
  local authenticated BOSS workflows and explicit platform-risk boundaries.
- [curl_cffi](https://github.com/lexiforest/curl_cffi): optional TLS
  impersonation capability; deliberately not a default dependency without a
  verified source need.
- [RFC 5861](https://www.rfc-editor.org/rfc/rfc5861): stale-while-revalidate and
  stale-if-error concepts used for explicit cache degradation.
- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents):
  task-specific, outcome-based evaluation.
- [LangSmith evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts):
  offline regression plus online observation.

References provide ideas, not copied claims. A proposed design must be validated
against JobFindsMe's real constraints and evidence.
