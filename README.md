# JobFindsMe

Agent-native, local-first job discovery and tracking.

JobFindsMe lets existing AI agents work with local resume facts, public or
user-provided job sources, deterministic matching, job states, and optional
monitoring. The core workflow needs no model API.

## Install

```bash
python3 -m pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git"
jobfindsme doctor
```

Connect one host:

```bash
jobfindsme install codex
jobfindsme install claude
jobfindsme install qwen
```

Restart the host, then ask it to use JobFindsMe. The bundled Skill tells the
agent to pass a resume path to the local Core instead of reading the complete
resume into model context.

## CLI

```bash
jobfindsme workspace init --name "My search"

jobfindsme plan add \
  --workspace <workspace_id> \
  --name "AI application engineer" \
  --role "AI application engineer" \
  --city "Shanghai"

jobfindsme jobs import \
  --workspace <workspace_id> \
  exported-jobs.json

jobfindsme jobs search \
  --workspace <workspace_id> \
  --plan <plan_id>
```

The MCP `search_jobs` tool can also discover from an explicit Greenhouse board,
public Schema.org `JobPosting` page, or local CSV/JSON file before matching.

## Data And Safety

- SQLite data stays under `~/.jobfindsme/` by default.
- Resume imports retain confirmed facts and minimum evidence, not complete text.
- Destructive deletion requires preview and a short-lived confirmation token.
- Recruitment sources must be public, exported by the user, or explicitly
  authorized. JobFindsMe does not bypass login, CAPTCHA, robots policy, or
  platform terms.

## Status

- 120-case synthetic regression dataset with machine-generated reports
- Initial end-to-end validation against a captured public official-source feed
- Compatibility candidates are not marked officially supported until a named
  client version passes a real field test

See [`PROJECT_SPEC.md`](PROJECT_SPEC.md) for scope and architecture.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

Licensed under the MIT License.
