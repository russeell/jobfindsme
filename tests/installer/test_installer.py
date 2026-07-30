from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

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


def test_connect_is_idempotent_and_refreshes_existing_config(tmp_path) -> None:
    service = installer(tmp_path)

    first = service.connect("workbuddy")
    second = service.connect("workbuddy")

    assert first.action == "connect"
    assert second.action == "connect"
    assert second.backups
    config = json.loads(Path(second.config_path).read_text())
    assert "jobfindsme" in config["mcpServers"]


def test_backup_names_do_not_collide_within_one_second(tmp_path) -> None:
    service = installer(tmp_path)
    service.install("qwen")

    first = service.upgrade("qwen")
    second = service.uninstall("qwen")

    assert first.backups[0] != second.backups[0]
    assert Path(first.backups[0]).exists()
    assert Path(second.backups[0]).exists()


@pytest.mark.parametrize("host", ["codex", "claude", "qwen"])
def test_upgrade_backs_up_and_uninstall_preserves_local_data(
    tmp_path,
    host,
) -> None:
    first = HostInstaller(
        home=tmp_path,
        python="/old/python",
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )
    first.install(host)
    database = tmp_path / ".jobfindsme" / "data" / "jobfindsme.db"
    database.write_text("personal data")

    upgraded = HostInstaller(
        home=tmp_path,
        python="/new/python",
        now=datetime(2026, 7, 29, tzinfo=UTC),
    ).upgrade(host)
    assert upgraded.action == "upgrade"
    assert "/new/python" in Path(upgraded.config_path).read_text()
    assert upgraded.backups

    removed = HostInstaller(
        home=tmp_path,
        python="/new/python",
        now=datetime(2026, 7, 30, tzinfo=UTC),
    ).uninstall(host)
    assert removed.action == "uninstall"
    assert "jobfindsme.mcp" not in Path(removed.config_path).read_text()
    assert not Path(removed.skill_path).exists()
    assert database.read_text() == "personal data"
