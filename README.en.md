# jobfindsme · AI Job Search Radar

**One sentence brings together jobs from BOSS直聘, 猎聘 (Liepin), 智联招聘 and 前程无忧, then filters and tracks them against your resume.**

[Chinese](README.md) · [Architecture](docs/architecture.md)

> ⭐ If jobfindsme saves you time, give it a star so more job seekers can find it.

## What it does

- searches **BOSS直聘、猎聘 (Liepin)、智联招聘、前程无忧** from one Agent;
- deterministically ranks jobs against structured local resume facts;
- returns matching jobs with direct apply links;
- host-Agent scheduled searches; applied jobs are never re-suggested;
- query every job ever matched, with its state.

### Evidence, not claims

| Release gate | Current result |
|---|---:|
| Python tests | 301 passing |
| Clean install + Cursor setup | 12 seconds |
| Agent behavior contract | 0/6 without the Skill, 6/6 with it |
| Wheel smoke test | CLI, SQLite migrations, and all 5 MCP tools pass end to end |

Live availability changes with platform controls and local login state.
jobfindsme never presents cache or a blocked response as fresh data; every
search returns per-source diagnostics. See the latest
[four-source search report](evaluation/evidence/latest_four_source_search.md).

## Install

### Option 1: just ask your Agent (recommended)

In Claude Code, Codex, Cursor, or ZCode, paste the whole sentence:

```text
Install jobfindsme by following the README at
https://github.com/russeell/jobfindsme, then use my local resume at
~/Documents/resume.pdf to find AI application engineer roles in
Shanghai, 20K+.
```

The Agent reads the repository README, installs the local runtime
(`curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh | bash`),
wires the MCP config (`jobfindsme connect <current-agent>`), asks you to
restart, and searches. First install takes a few minutes; if the Agent
cannot reach the network, use Option 2.

### Option 2: manual (about 1 minute)

Install the local runtime once (Python 3.11+):

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh | bash
```

Wire the MCP config to your Agent, then restart it:

```bash
jobfindsme connect claude      # Claude Code
jobfindsme connect codex       # Codex
jobfindsme connect cursor      # Cursor
jobfindsme connect zcode       # ZCode
```

Other MCP clients: `jobfindsme config` prints the standard JSON to paste, or
`jobfindsme connect --path <file>` writes it directly. The `.mcp.json` at the
repo root is the same standard config.

Self-check, then start:

```bash
jobfindsme doctor
```

## Use

```text
Use jobfindsme and my local resume at ~/Documents/resume.pdf
to find full-time AI application engineer roles in Shanghai and Hangzhou,
20K+ monthly salary, experienced hiring.
```

Later:

```text
Find new jobs since my last search.
```

## Sources

Four source paths are maintained — **BOSS直聘**, **猎聘 (Liepin)**,
**智联招聘**, and **前程无忧**.
The project prioritizes useful, reliable results over an inflated connector
count and does not claim complete market coverage.

| Source | Method | Speed | Browser needed? |
|---|---|---|---|
| BOSS Zhipin | authorized local Chrome session with time-labeled cache fallback | login-dependent | yes |
| Liepin | public Web JSON listing with bounded detail enrichment | usually sub-second | no for listings |
| Zhaopin | HTTP first, authorized local-browser fallback after security checks | experimental | fallback only |
| 51job | HTTP first, authorized local-browser fallback after WAF checks | experimental | fallback only |

HTTP sources can degrade to an explicitly labeled recent cache when challenged.
When Chrome is available, bounded browser fallbacks may enrich results. BOSS
requires an authenticated local Chrome session.

## Privacy and limitations

- resumes, plans, and job state remain in local SQLite;
- the Agent receives a resume path, not the complete resume text;
- job descriptions are untrusted external content;
- the ranking score is explainable and reproducible, not a hiring probability;
- the project does not auto-apply or guarantee complete market coverage.

See [architecture](docs/architecture.md) for the module map and the
search path, [connectors](docs/connectors.md) for source promotion
gates, and [evaluation](docs/evaluation.md) for the quality loop. The
full engineering spec lives in `docs/internal/project_spec.md`.

## License

[MIT](LICENSE)
