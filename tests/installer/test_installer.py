from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import pytest

from jobfindsme.installer import HostInstaller

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def installer(home):
    return HostInstaller(
        home=home,
        python=sys.executable,
        now=NOW,
    )


@pytest.mark.parametrize(
    ("host", "config_relative", "skill_relative"),
    [
        (
            "codex",
            ".codex/config.toml",
            ".codex/skills/jobfindsme/SKILL.md",
        ),
        (
            "claude",
            ".claude.json",
            ".claude/skills/jobfindsme/SKILL.md",
        ),
        (
            "qwen",
            ".qwen/settings.json",
            ".qwen/skills/jobfindsme/SKILL.md",
        ),
    ],
)
def test_one_command_install_writes_config_and_full_skill(
    tmp_path, host, config_relative, skill_relative
) -> None:
    result = installer(tmp_path).install(host)

    config = tmp_path / config_relative
    skill = tmp_path / skill_relative
    assert result.host == host
    assert config.exists()
    assert skill.exists()
    assert "Never read" in skill.read_text()
    assert "complete resume" in skill.read_text()
    assert str(sys.executable) in config.read_text()


def test_json_install_preserves_existing_config_and_creates_backup(tmp_path) -> None:
    config = tmp_path / ".qwen" / "settings.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"theme": "dark"}))

    result = installer(tmp_path).install("qwen")

    document = json.loads(config.read_text())
    assert document["theme"] == "dark"
    assert "jobfindsme" in document["mcpServers"]
    assert len(result.backups) == 1
    backup = config.with_name("settings.json.backup-20260728T000000Z")
    assert json.loads(backup.read_text()) == {"theme": "dark"}


def test_install_refuses_to_silently_replace_existing_server(tmp_path) -> None:
    service = installer(tmp_path)
    service.install("claude")

    with pytest.raises(FileExistsError):
        service.install("claude")
