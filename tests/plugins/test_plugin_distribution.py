from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_all_host_manifests_share_identity_version_and_skill_source() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    manifests = (
        _json(".codex-plugin/plugin.json"),
        _json(".claude-plugin/plugin.json"),
        _json(".cursor-plugin/plugin.json"),
    )

    assert {manifest["name"] for manifest in manifests} == {"jobfindsme"}
    assert {manifest["version"] for manifest in manifests} == {version}
    assert {manifest["skills"] for manifest in manifests} == {"./skills/"}
    assert {manifest["mcpServers"] for manifest in manifests} == {"./.mcp.json"}
    assert (ROOT / "skills/jobfindsme/SKILL.md").is_file()


def test_packaged_skill_is_generated_from_canonical_skill() -> None:
    canonical = (ROOT / "skills/jobfindsme/SKILL.md").read_bytes()
    packaged = (ROOT / "src/jobfindsme/resources/jobfindsme/SKILL.md").read_bytes()

    assert packaged == canonical


def test_native_plugins_share_one_mcp_definition() -> None:
    codex = _json(".codex-plugin/plugin.json")
    cursor = _json(".cursor-plugin/plugin.json")
    mcp = _json(".mcp.json")

    assert codex["mcpServers"] == "./.mcp.json"
    assert cursor["mcpServers"] == "./.mcp.json"
    server = mcp["mcpServers"]["jobfindsme"]
    assert server["command"] == "bash"
    assert "jobfindsme.mcp" in " ".join(server["args"])
    assert "config.toml" not in json.dumps(mcp)
    assert ".claude.json" not in json.dumps(mcp)


def test_marketplaces_point_to_the_repository_plugin() -> None:
    codex = _json(".agents/plugins/marketplace.json")
    claude = _json(".claude-plugin/marketplace.json")

    assert codex["plugins"][0]["name"] == "jobfindsme"
    assert codex["plugins"][0]["source"] == {"source": "url", "url": "./"}
    assert claude["plugins"][0]["name"] == "jobfindsme"
    assert claude["plugins"][0]["source"] == "./"
