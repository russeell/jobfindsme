# Development

## Setup

```bash
python -m pip install -e ".[dev,browser]"
```

Or with uv (local convenience; CI uses pip):

```bash
uv sync --extra dev --extra browser
```

> If PyPI is unreachable, `uv sync --offline` reconciles from the local
> cache; `uv run --offline python -m pytest` also works.  Plain
> `.venv/bin/python -m pytest` never touches the network.

## Quality gates

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
bash scripts/smoke_installed_package.sh   # built-wheel sanity
python scripts/sync_skill.py --check       # canonical Skill matches wheel copy
```

CI (`ci.yml`) runs tests on Python 3.11/3.12/3.13 plus the synthetic
evaluation regression gate, the clean-install smoke test, and the Agent
behavior RED/GREEN contract in `evaluation/agent_behavior/data/`.

## Changing Agent behavior

Edit only `skills/jobfindsme/SKILL.md`, then generate the packaged wheel copy:

```bash
python scripts/sync_skill.py
python -m pytest tests/plugins tests/evaluation/test_agent_behavior.py
```

The same Skill is consumed by the Codex, Claude, and Cursor plugin manifests.
The old host-specific `connect` installer is a compatibility adapter, not a
second Skill source. Fixture behavior tests are deterministic CI evidence;
cross-Agent release claims require redacted `live_agent` transcripts from all
three hosts. See `evaluation/agent_behavior/data/README.md`.

## Release

Version lives in `pyproject.toml`, `scripts/install.sh`, and the git
tag (release workflow verifies they match). A `release` run builds the
wheel, verifies it contains no retired modules, runs the installed-
package smoke, and publishes the GitHub release.

## Changing the tool surface

Tools are defined in `mcp/registry.py` (definitions + schemas), use
cases live in `mcp/handlers/`, response assembly in `mcp/responses.py`.
Add a tool by: 1) input/output models in `mcp/schemas.py`, 2) a
`ToolDefinition`, 3) a handler in the right `handlers/*.py` module.
Update the tool-count assertions in `tests/` (`test_stdio_server.py`,
`test_doctor.py`, `test_tools.py`) and the `_INSTRUCTIONS` contract in
`mcp/server.py` if the user-facing workflow changes.

## Contributing

See `CONTRIBUTING.md` for taxonomy rules and PR guidance.
