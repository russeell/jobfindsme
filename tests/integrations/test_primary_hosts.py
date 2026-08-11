from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_primary_host_configs_launch_the_same_local_stdio_server() -> None:
    mcp = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["jobfindsme"]
    assert mcp["command"] == "bash"
    assert "jobfindsme.mcp" in " ".join(mcp["args"])

    # Every host uses the same standard MCP config in the repo root
    assert (ROOT / ".mcp.json").is_file()


def test_shared_skill_encodes_privacy_and_minimum_question_policy() -> None:
    shared = (ROOT / "skills" / "jobfindsme" / "SKILL.md").read_text()

    required_phrases = [
        "Never read",
        "complete resume",
        "setup_profile",
        "Ask only when a missing constraint",
        "auto_confirm: false",
        "Never ask ordinary users",
        "delete_local_data",
        "action: preview",
        "action: confirm",
        "Never invent",
    ]
    assert all(phrase in shared for phrase in required_phrases)

    # v0.5 output contract enforcement phrases
    output_contract_phrases = [
        "FINAL USER-FACING OUTPUT",
        "verbatim",
        "STRICTLY FORBIDDEN",
        "龙头",
        "有前景",
        "福利齐全",
    ]
    for phrase in output_contract_phrases:
        assert phrase in shared, f"Missing contract phrase: {phrase}"


def test_mcp_server_instructions_declare_text_as_final_output() -> None:
    """The MCP server instructions must declare content[0].text as final."""
    from jobfindsme.mcp.server import _INSTRUCTIONS

    assert "FINAL USER-FACING OUTPUT" in _INSTRUCTIONS
    assert "verbatim" in _INSTRUCTIONS
    assert "never renumber" in _INSTRUCTIONS.casefold()
    assert "龙头" in _INSTRUCTIONS
    assert "jobfindsme setup" in _INSTRUCTIONS
    assert "jobfindsme doctor" in _INSTRUCTIONS


def test_search_jobs_tool_description_declares_text_immutability() -> None:
    """The search_jobs tool description must state the text contract."""
    from jobfindsme.mcp.registry import TOOL_DEFINITIONS

    search_def = [t for t in TOOL_DEFINITIONS if t.name == "search_jobs"][0]
    desc = search_def.description

    assert "content[0].text" in desc
    assert "FINAL USER-FACING OUTPUT" in desc
    assert "verbatim" in desc


def test_primary_hosts_share_one_discoverable_skill() -> None:
    content = (ROOT / "skills" / "jobfindsme" / "SKILL.md").read_text()

    assert content.startswith("---\nname: jobfindsme\n")
    assert "Never read" in content
    assert not (ROOT / "integrations" / "shared" / "SKILL.md").exists()
