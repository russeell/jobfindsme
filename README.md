# JobFindsMe

JobFindsMe is an agent-native, local-first job discovery and tracking engine.

> Let your existing AI agent find, match, and track jobs from official career
> sites while your resume and application history stay local.

## Product Boundary

V0.1 consists of:

- a deterministic Python Core;
- a local SQLite workspace;
- a CLI fallback;
- a local stdio MCP server;
- Codex and Claude Code skills;
- official-site connectors;
- reproducible evaluation.

V0.1 does not require a model API, does not run a public Web SaaS, and does not
implement a custom agent runtime. The archived Web prototype lives next to this
repository as `jobfindsme-web-prototype`.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

Initialize a local workspace:

```bash
jobfindsme workspace init
jobfindsme plan add --name "杭州 AI 应用工程师" --role "AI应用工程师" --city "杭州"
jobfindsme plan list
```

The complete product, architecture, security, and milestone baseline is in
`PROJECT_SPEC.md`. Executable work is tracked in `specs/feature_list.json`.
