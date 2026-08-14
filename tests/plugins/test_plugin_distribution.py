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


def test_plugin_marketplace_manifests_are_present_and_valid() -> None:
    """Native plugin marketplaces (Codex / Claude Code / Agents / Cursor)
    must ship manifests with the project name and matching version."""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    manifests = [
        ROOT / ".codex-plugin/plugin.json",
        ROOT / ".claude-plugin/marketplace.json",
        ROOT / ".claude-plugin/plugin.json",
        ROOT / ".agents/plugins/marketplace.json",
        ROOT / ".cursor-plugin/plugin.json",
    ]
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "jobfindsme"
        if "version" in data:
            assert data["version"] == version, path
    # Marketplace plugin entries must reference the same name.
    for path in (
        ROOT / ".claude-plugin/marketplace.json",
        ROOT / ".agents/plugins/marketplace.json",
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert all(p["name"] == "jobfindsme" for p in data["plugins"])


def test_install_script_and_readme_are_version_agnostic() -> None:
    """Releases must not require touching install.sh or README per version."""
    install = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    assert "releases/latest" in install
    # A pinned wheel URL would break the next release without an edit.
    assert "releases/download/v0.10.0" not in install

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "scripts/install.sh" in readme
    assert "releases/latest" in readme
    assert "jobfindsme-0.10.0-py3-none-any.whl" not in readme
