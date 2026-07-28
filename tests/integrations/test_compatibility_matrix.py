from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
COMPATIBILITY = ROOT / "integrations" / "compatibility"


def load(path: Path):
    return json.loads(path.read_text())


def test_all_candidate_clients_use_the_same_stdio_command() -> None:
    cursor = load(COMPATIBILITY / "cursor" / "mcp.json.template")["mcpServers"][
        "jobfindsme"
    ]
    cline = load(COMPATIBILITY / "cline" / "cline_mcp_settings.json.template")[
        "mcpServers"
    ]["jobfindsme"]
    roo = load(COMPATIBILITY / "roo" / "mcp.json.template")["mcpServers"]["jobfindsme"]
    opencode = load(COMPATIBILITY / "opencode" / "opencode.json.template")["mcp"][
        "jobfindsme"
    ]
    cherry = load(COMPATIBILITY / "cherry-studio" / "manual.json.template")

    for config in (cursor, cline, roo, cherry):
        assert config["command"] == "__PYTHON__"
        assert config["args"] == ["-m", "jobfindsme.mcp"]
    assert opencode["command"] == [
        "__PYTHON__",
        "-m",
        "jobfindsme.mcp",
    ]
    assert cline["autoApprove"] == []
    assert roo["alwaysAllow"] == []


def test_shared_suite_covers_protocol_privacy_and_deletion() -> None:
    scenarios = load(COMPATIBILITY / "scenarios.json")["scenarios"]

    assert len(scenarios) == 7
    assert any("resume_path" in item for item in scenarios)
    assert any("delete" in item for item in scenarios)
    assert any("product_tools" in item for item in scenarios)
    assert any("untrusted" in item for item in scenarios)


def test_no_client_is_claimed_supported_before_a_real_field_test() -> None:
    report = load(ROOT / "reports" / "compatibility" / "v0.1.json")

    assert {item["client"] for item in report["clients"]} == {
        "Cursor",
        "Cline",
        "Roo Code",
        "OpenCode",
        "Cherry Studio",
    }
    for item in report["clients"]:
        assert item["status"] == "contract_tested"
        assert item["officially_supported"] is False
        assert item["field_tested_version"] is None
