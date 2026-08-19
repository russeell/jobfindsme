# jobfindsme product and engineering specification

## 1. Product goal

`jobfindsme` is a local-first job discovery and tracking MCP Server. It helps
an existing AI Agent search BOSS直聘、猎聘、智联招聘 and 前程无忧, remove repeats, enforce user
constraints, preserve job state, and return compact evidence with direct apply
links.

The user-facing promise is simple:

```text
local resume path + one natural-language request
-> qualified jobs from maintained sources
-> later searches report useful changes instead of repeating the same list
```

Success is measured by qualified unseen jobs, time to first useful result,
ranking quality, valid links, source health, and interaction count. Connector
count and raw records are not product outcomes.

## 2. Scope

### In scope

- local resume parsing into reviewable structured facts;
- a single local profile snapshot and one set of preferences (no reusable
  search plans or active-workspace product concepts);
- BOSS直聘 discovery through a user-authorized local Chrome session;
- 猎聘 discovery through HTTP, with bounded browser detail enrichment;
- 智联招聘 and 前程无忧 discovery through HTTP, with bounded browser fallback;
- normalization, cross-source deduplication, hard filtering, and coarse ranking;
- incremental states: new, changed, reopened, closed, seen, saved, applied,
  and rejected;
- local SQLite persistence, export, and two-phase deletion;
- CLI for installation, diagnostics, local profile import, and administration;
- local stdio MCP Server for Agent integration;
- repeatable tests and field evaluation.

### Out of scope

- automatic job application;
- hosted Web SaaS or a custom Agent runtime;
- a built-in scheduler or notification provider;
- bypassing captchas, platform controls, or access permissions;
- claiming complete market coverage or hiring probability;
- requiring a model API key for core behavior.

Scheduling, notification delivery, and conversation belong to the host Agent.
`jobfindsme` owns facts, state, hard constraints, deterministic ordering, and
the stable base result. The host may add an explanation but cannot invent or
silently reorder evidence.

## 3. System boundaries

```text
Host Agent
  -> jobfindsme Skill
  -> stdio MCP adapter
  -> jobfindsme core
       -> profile and search-plan services
       -> SearchOrchestrator
            -> source connectors
            -> normalization and repository
            -> hard filters and deterministic matcher
            -> impressions and incremental changes
       -> state and privacy services
  -> local SQLite

CLI -> the same jobfindsme core
```

Dependency direction is one way:

```text
CLI / MCP -> core -> domain services -> connector and storage adapters
```

Core must not import MCP, an Agent SDK, a hosted model provider, FastAPI, or a
notification SDK. Web and MCP adapters must not duplicate matching rules.

## 4. Source strategy

Four source paths are maintained:

| Source | Primary path | Fallback | Role |
|---|---|---|---|
| BOSS直聘 | authorized local Chrome CDP | recent labeled cache | primary live source |
| 猎聘 | HTTP JSON | bounded CDP detail enrichment, then cache | independent second source |
| 智联招聘 | HTTP JSON | bounded CDP request, then cache | additional coverage |
| 前程无忧 | HTTP JSON | bounded CDP request, then cache | additional coverage |

Historical enum values and migrations may remain for old SQLite databases, but
retired sources must not be selected, diagnosed, documented as supported, or
executed by the current catalog.

Every source run records status, method, duration, records discovered, cache
usage, and a bounded error. One source failure must not cancel successful
results from another source.

Platform search pages are partial snapshots. Their missing records must never
be treated as closure evidence; only an explicitly complete authoritative
snapshot may close jobs by absence.

## 5. Core search flow

```text
resolve active context (internal) and preferences
-> select refresh sources
-> discover sources concurrently
-> validate and normalize source records
-> update source provenance and canonical jobs
-> apply hard constraints
-> deterministic coarse ranking
-> compare with impressions and state history
-> return compact summaries, evidence, changes, and diagnostics
```

Hard constraints include location, salary, experience when known,
recruitment track, employment type, exclusions, and target-role eligibility.
Unknown source fields must be labeled unknown rather than guessed.

An explicit salary constraint defaults to `strict`: a job without comparable
salary evidence is excluded and counted in diagnostics. Users may explicitly
choose `include_undisclosed`; those jobs remain candidates with a warning. The
system never treats an undisclosed salary as satisfying the requested amount.

Skill aliases are loaded from the versioned packaged taxonomy at
`resources/taxonomy/skills.json`. Contributions must pass collision validation.
The default remains deterministic and model-free; embeddings are not a hidden
runtime dependency.

The deterministic score is an explainable ordering signal, not a hiring
probability. The Server owns facts, filtering, ranking, and a compact factual
summary; the host Agent organizes the final user-facing expression from those
facts only and never invents jobs, salary, links, scores, or reasons.

## 6. MCP contract

The server name and all public product identifiers use lowercase `jobfindsme`.
The MCP surface contains five focused tools:

1. `setup` — profile snapshot import and preferences configuration
2. `search_jobs`
3. `get_jobs` — list/paginate, or pass `job_id` for one job's full details
4. `update_job_state`
5. `delete_local_data`

Every tool must provide:

- a unique name, title, narrow description, and strict Pydantic input schema;
- an `outputSchema` and validated `structuredContent`;
- accurate read-only, destructive, idempotent, and open-world annotations;
- bounded text output so the host context is not flooded;
- actionable execution errors returned as tool errors rather than protocol
  failures.

Human-facing `content` carries a compact factual summary. The same response
also carries validated `structuredContent` — bounded structured facts in
`jobs` (title, company, location, salary, score, evidence, change state,
apply URL; no full JD text) plus `count`, `changes`, and
`diagnostic_summary`. Clients that need full job details must use `get_jobs`
instead (passing `job_id` for one job's full details).

`search_jobs` returns bounded structured facts plus a compact five-part
factual baseline (the summary), in this order:

```text
resume usage -> source diagnostics -> applied filters -> job blocks -> changes
```

Each job block contains facts, an explainable match signal, bounded warnings,
a bare apply URL, and a grounded recommendation reason. The host Agent builds
the final answer from the returned facts only — never inventing jobs, salary,
links, scores, or reasons, and keeping every apply URL exactly as returned.
A separate evidence-grounded comparison is allowed only when the user asks
for one. No-resume mode remains explicit.

Search-plan salary bounds use the domestic recruiting convention of monthly
salary in thousands of CNY. Bonus months such as `18-30K·15薪` do not turn an
18K monthly lower bound into a match for `salary_min_k=20`; conflicting raw and
structured salary fields are reconciled conservatively.
An empty incremental result is a successful radar outcome when unchanged jobs
were suppressed; it must not be renamed as duplicate detection or trigger an
automatic full refresh. If MCP is unavailable, the host may run `jobfindsme
doctor` for diagnosis, but must not invent a CLI search workflow or expose
workspace and plan identifiers.

`delete_local_data` always uses preview then a hashed, SQLite-backed,
single-use confirmation token with a short TTL. It remains valid across stdio
server restarts. Export writes
to a local file and returns only path, hash, and record counts. External JD
content is untrusted data and must never be treated as instructions.

## 7. Data and privacy

SQLite is the source of truth for workspaces, profiles, search plans, source
subscriptions, canonical jobs, source provenance, impressions, and job-state
events. Existing migrations are append-only compatibility history.

Default resume flow:

```text
local file path -> local extraction -> structured facts -> confirmation
-> source text discarded -> only facts, evidence snippets, and hash retained
```

No connector may receive resume content. Workspace-scoped records must not leak
across workspaces. User data is exportable and deletable without a hosted
service.

## 8. Quality loop

The fast loop runs on every change:

```text
focused tests -> full pytest -> synthetic evaluation gate
-> Ruff check -> Ruff format check -> installed-wheel smoke test
```

The product loop uses real, manually reviewed results:

```text
real search snapshot
-> label relevance, liveness, link validity, duplicate and filter errors
-> compute P@10, NDCG@10, valid-link rate, source success, latency
-> classify bad case by source / normalization / filter / rank / presentation
-> create one bounded feature
-> rerun regression and a fresh snapshot
```

Synthetic data is valid for regression only and cannot support public quality
claims. A seven-day trial is useful for incremental behavior, but it is not a
prerequisite for each fix: one labeled snapshot is the default fast feedback
unit.

The historical BM25 algorithm lives only under `evaluation/legacy_matcher.py`
for snapshot compatibility. Production search uses the typed filter and signal
ranking functions in `matching.py`.

Retired source enum values remain readable solely for old SQLite workspaces.
The active catalog rejects them, and the next major schema migration may remove
them after a measured compatibility window.

## 9. Definition of done

A feature is done only when:

- its behavior and boundary are stated before implementation;
- the change is scoped to declared paths;
- focused and full tests pass;
- Ruff check and format check pass;
- public contracts and docs match executable behavior;
- evidence is generated by the Harness;
- no metric, source, or capability is claimed without reproducible evidence.

## 10. Design references

Before a high-impact design change, review at least one primary specification
and one relevant maintained implementation. Record adopted and rejected ideas
in the active feature rather than accumulating separate research documents.

- [MCP architecture](https://modelcontextprotocol.io/specification/2025-06-18/architecture)
- [MCP tools schema](https://modelcontextprotocol.io/specification/2025-11-25/schema)
- [MCP server guide](https://modelcontextprotocol.io/docs/develop/build-server)
- [MCP client best practices](https://modelcontextprotocol.io/docs/develop/clients/client-best-practices)
- [JobSpy](https://github.com/speedyapply/JobSpy)
- [mcp-jobs](https://github.com/mergedao/mcp-jobs)

References inform design; local privacy, platform access, Chinese job fields,
and repeatable evidence decide what `jobfindsme` actually adopts.
