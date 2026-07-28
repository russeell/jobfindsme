# JobFindsMe

JobFindsMe is an agent-native, local-first job discovery and tracking engine.

It helps AI agents find, match, and track jobs using a local resume or a natural
language description.

## Core Features

- Local resume and job-search profiles
- Official career-site and supported job-platform sources
- Deterministic filtering, ranking, and evidence
- Local SQLite storage
- CLI and MCP interfaces
- No model API required

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

```bash
jobfindsme workspace init
jobfindsme plan add \
  --workspace <workspace_id> \
  --name "AI application engineer" \
  --role "AI application engineer" \
  --city "Shanghai"
jobfindsme plan list --workspace <workspace_id>
```

See `PROJECT_SPEC.md` for the product and architecture specification.
