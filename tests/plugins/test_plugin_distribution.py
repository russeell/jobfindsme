from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_single_standard_mcp_config_is_present_and_correct() -> None:
    """One standard MCP config in the repo root is the single source of truth."""
    mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["jobfindsme"]
    assert server["command"] == "bash"
    assert "jobfindsme.mcp" in " ".join(server["args"])
    assert "config.toml" not in json.dumps(mcp)
    assert ".claude.json" not in json.dumps(mcp)


def test_packaged_skill_is_generated_from_canonical_skill() -> None:
    canonical = (ROOT / "skills/jobfindsme/SKILL.md").read_bytes()
    packaged = (ROOT / "src/jobfindsme/resources/jobfindsme/SKILL.md").read_bytes()

    assert packaged == canonical


def test_cli_config_prints_a_valid_standard_mcp_json() -> None:
    from jobfindsme.cli import _mcp_json_config

    config = _mcp_json_config()
    server = config["mcpServers"]["jobfindsme"]
    # Either the current interpreter or the bash wrapper is acceptable —
    # both launch the same local stdio MCP server.
    assert "jobfindsme.mcp" in " ".join(server["args"])


def test_project_version_is_consistent_across_package_and_docs() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]
    wheel = f"jobfindsme-{version}-py3-none-any.whl"
    readme = (ROOT / "README.md").read_text()
    assert wheel in readme
