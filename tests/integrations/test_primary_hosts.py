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
        "setup",
        "Ask only when a missing constraint",
        "Never ask ordinary users",
        "delete_local_data",
        "action: preview",
        "action: confirm",
        "Never invent",
    ]
    assert all(phrase in shared for phrase in required_phrases)

    # Step 2 output contract phrases: facts ground the answer, no fabrication
    output_contract_phrases = [
        "structuredContent.jobs",
        "bare URL",
        "never invent jobs",
        "STRICTLY FORBIDDEN",
        "龙头",
        "有前景",
        "福利齐全",
    ]
    for phrase in output_contract_phrases:
        assert phrase in shared, f"Missing contract phrase: {phrase}"


def test_mcp_server_instructions_ground_answers_in_facts() -> None:
    """The MCP server instructions must ground answers in returned facts."""
    from jobfindsme.mcp.server import _INSTRUCTIONS

    assert "structuredContent.jobs" in _INSTRUCTIONS
    assert "bare URL" in _INSTRUCTIONS
    assert "never invent jobs" in _INSTRUCTIONS
    assert "龙头" in _INSTRUCTIONS
    assert "jobfindsme setup" in _INSTRUCTIONS
    assert "jobfindsme doctor" in _INSTRUCTIONS


def test_search_jobs_tool_description_declares_facts_contract() -> None:
    """The search_jobs tool description must state the facts contract."""
    from jobfindsme.mcp.registry import TOOL_DEFINITIONS

    search_def = [t for t in TOOL_DEFINITIONS if t.name == "search_jobs"][0]
    desc = search_def.description

    assert "structuredContent.jobs" in desc
    assert "never invent jobs" in desc
    assert "bare URL" in desc


def test_primary_hosts_share_one_discoverable_skill() -> None:
    content = (ROOT / "skills" / "jobfindsme" / "SKILL.md").read_text()

    assert content.startswith("---\nname: jobfindsme\n")
    assert "Never read" in content
    assert not (ROOT / "integrations" / "shared" / "SKILL.md").exists()
