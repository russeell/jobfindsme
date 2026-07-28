from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]
INTEGRATIONS = ROOT / "integrations"


def test_primary_host_configs_launch_the_same_local_stdio_server() -> None:
    codex = tomllib.loads(
        (INTEGRATIONS / "codex" / "config.toml.template").read_text()
    )["mcp_servers"]["jobfindsme"]
    claude = json.loads((INTEGRATIONS / "claude" / ".mcp.json.template").read_text())[
        "mcpServers"
    ]["jobfindsme"]
    qwen = json.loads((INTEGRATIONS / "qwen" / "settings.json.template").read_text())[
        "mcpServers"
    ]["jobfindsme"]

    for config in (codex, claude, qwen):
        assert config["command"] == "__PYTHON__"
        assert config["args"] == ["-m", "jobfindsme.mcp"]
        assert config["env"]["PYTHONPATH"] == "__PROJECT_ROOT__/src"
        assert config["env"]["JOBFINDSME_DB_PATH"].endswith("jobfindsme.db")
    assert qwen["trust"] is False
    assert codex["default_tools_approval_mode"] == "prompt"


def test_shared_skill_encodes_privacy_and_minimum_question_policy() -> None:
    shared = (INTEGRATIONS / "shared" / "SKILL.md").read_text()

    required_phrases = [
        "Never read",
        "complete resume",
        "setup_profile",
        "Ask only for missing constraints",
        "delete_local_data",
        "action: preview",
        "action: confirm",
        "Never invent",
    ]
    assert all(phrase in shared for phrase in required_phrases)


def test_each_primary_host_ships_a_discoverable_skill() -> None:
    paths = [
        INTEGRATIONS / "codex" / "skills" / "jobfindsme" / "SKILL.md",
        INTEGRATIONS / "claude" / "skills" / "jobfindsme" / "SKILL.md",
        INTEGRATIONS / "qwen" / "skills" / "jobfindsme" / "SKILL.md",
    ]

    for path in paths:
        content = path.read_text()
        assert content.startswith("---\nname: jobfindsme\n")
        assert "integrations/shared/SKILL.md" in content
