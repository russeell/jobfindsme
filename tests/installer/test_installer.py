from __future__ import annotations

import json
import sys
import tomllib
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


def configured_python(config: Path, host: str) -> str:
    content = config.read_text(encoding="utf-8")
    if host == "codex":
        return tomllib.loads(content)["mcp_servers"]["agent-job-search"]["command"]
    return json.loads(content)["mcpServers"]["agent-job-search"]["command"]


@pytest.mark.parametrize(
    ("host", "config_relative", "skill_relative"),
    [
        (
            "codex",
            ".codex/config.toml",
            ".codex/skills/agent-job-search/SKILL.md",
        ),
        (
            "claude",
            ".claude.json",
            ".claude/skills/agent-job-search/SKILL.md",
        ),
        (
            "cursor",
            ".cursor/mcp.json",
            ".cursor/skills/agent-job-search/SKILL.md",
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
    assert "Never read" in skill.read_text(encoding="utf-8")
    assert "complete resume" in skill.read_text(encoding="utf-8")
    assert configured_python(config, host) == str(sys.executable)


def test_json_install_preserves_existing_config_and_creates_backup(tmp_path) -> None:
    config = tmp_path / ".cursor" / "mcp.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

    result = installer(tmp_path).install("cursor")

    document = json.loads(config.read_text(encoding="utf-8"))
    assert document["theme"] == "dark"
    assert "agent-job-search" in document["mcpServers"]
    assert len(result.backups) == 1
    backup = config.with_name("mcp.json.backup-20260728T000000Z")
    assert json.loads(backup.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_install_refuses_to_silently_replace_existing_server(tmp_path) -> None:
    service = installer(tmp_path)
    service.install("claude")

    with pytest.raises(FileExistsError):
        service.install("claude")


def test_connect_is_idempotent_and_refreshes_existing_config(tmp_path) -> None:
    service = installer(tmp_path)

    first = service.connect("cursor")
    second = service.connect("cursor")

    assert first.action == "connect"
    assert second.action == "connect"
    assert second.backups
    config = json.loads(Path(second.config_path).read_text(encoding="utf-8"))
    assert "agent-job-search" in config["mcpServers"]


def test_backup_names_do_not_collide_within_one_second(tmp_path) -> None:
    service = installer(tmp_path)
    service.install("cursor")

    first = service.upgrade("cursor")
    second = service.uninstall("cursor")

    assert first.backups[0] != second.backups[0]
    assert Path(first.backups[0]).exists()
    assert Path(second.backups[0]).exists()


def test_fast_installer_matches_package_version_and_verifies_wheel() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    script = (root / "scripts" / "install.sh").read_text(encoding="utf-8")

    # Offline fallback pin must match the package version; the live path
    # resolves the latest release dynamically so releases need no script edit.
    assert f'PINNED_VERSION="{version}"' in script
    assert "releases/latest" in script
    assert "CHECKSUM_GH=" in script
    assert "SHA-256 校验失败" in script
    assert "ghproxy" not in script
    # The installer must put jobfindsme on PATH after installation.
    assert "$HOME/.local/bin" in script or "LAUNCHER" in script


@pytest.mark.parametrize("host", ["codex", "claude", "cursor"])
def test_upgrade_backs_up_and_uninstall_preserves_local_data(
    tmp_path,
    host,
) -> None:
    old_python = tmp_path / "old-python"
    new_python = tmp_path / "new-python"
    first = HostInstaller(
        home=tmp_path,
        python=old_python,
        now=datetime(2026, 7, 28, tzinfo=UTC),
    )
    first.install(host)
    database = tmp_path / ".agent-job-search" / "data" / "agent-job-search.db"
    database.write_text("personal data", encoding="utf-8")

    upgraded = HostInstaller(
        home=tmp_path,
        python=new_python,
        now=datetime(2026, 7, 29, tzinfo=UTC),
    ).upgrade(host)
    assert upgraded.action == "upgrade"
    assert configured_python(Path(upgraded.config_path), host) == str(new_python)
    assert upgraded.backups

    removed = HostInstaller(
        home=tmp_path,
        python=new_python,
        now=datetime(2026, 7, 30, tzinfo=UTC),
    ).uninstall(host)
    assert removed.action == "uninstall"
    assert "jobfindsme.mcp" not in Path(removed.config_path).read_text(encoding="utf-8")
    assert not Path(removed.skill_path).exists()
    assert database.read_text(encoding="utf-8") == "personal data"


@pytest.mark.parametrize("host", ["codex", "claude", "cursor"])
def test_connect_migrates_legacy_config_and_reuses_legacy_data(
    tmp_path,
    host,
) -> None:
    legacy_data = tmp_path / ".jobfindsme" / "data"
    legacy_data.mkdir(parents=True)
    legacy_database = legacy_data / "jobfindsme.db"
    legacy_database.write_text("legacy history", encoding="utf-8")
    # The renamed installer creates its runtime root before `connect`; that
    # must not make the existing data disappear from the selected config.
    (tmp_path / ".agent-job-search" / "runtime").mkdir(parents=True)

    service = installer(tmp_path)
    config_path, legacy_skill = {
        "codex": (
            tmp_path / ".codex" / "config.toml",
            tmp_path / ".codex" / "skills" / "jobfindsme" / "SKILL.md",
        ),
        "claude": (
            tmp_path / ".claude.json",
            tmp_path / ".claude" / "skills" / "jobfindsme" / "SKILL.md",
        ),
        "cursor": (
            tmp_path / ".cursor" / "mcp.json",
            tmp_path / ".cursor" / "skills" / "jobfindsme" / "SKILL.md",
        ),
    }[host]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_skill.parent.mkdir(parents=True, exist_ok=True)
    legacy_skill.write_text("legacy skill", encoding="utf-8")
    if host == "codex":
        config_path.write_text(
            "\n[mcp_servers.jobfindsme]\ncommand = 'python'\nargs = []\n",
            encoding="utf-8",
        )
    else:
        config_path.write_text(
            json.dumps({"mcpServers": {"jobfindsme": {"command": "python"}}}),
            encoding="utf-8",
        )

    result = service.connect(host)
    content = Path(result.config_path).read_text(encoding="utf-8")

    assert "agent-job-search" in content
    assert "jobfindsme.db" in content
    assert not legacy_skill.exists()
    assert legacy_database.read_text(encoding="utf-8") == "legacy history"
