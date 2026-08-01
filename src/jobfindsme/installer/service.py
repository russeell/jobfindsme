from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from pydantic import Field

from jobfindsme.contracts import StrictModel


class InstallResult(StrictModel):
    host: str
    action: str
    config_path: str
    skill_path: str
    backups: tuple[str, ...] = ()
    commands: tuple[str, ...] = Field(default_factory=tuple)


# Core hosts with code-level adapters (config formats differ).
# Everything else: use `jobfindsme config` (standard mcpServers JSON) or
# `jobfindsme connect --path <file>` for any client. Aligned with the
# mainstream 2-4 client approach of popular MCP projects.
# Claude covers both Claude Desktop and Claude Code (~/.claude.json).
_STANDARD_JSON_HOSTS: dict[str, tuple[str, str]] = {
    "claude": (".claude.json", ".claude/skills"),
    "cursor": (".cursor/mcp.json", ".cursor/skills"),
}


class HostInstaller:
    HOSTS = {
        "codex",
        "claude",
        "cursor",
        "zcode",  # developer-host, kept for the project's own usage
    }

    def __init__(
        self,
        *,
        home: str | Path | None = None,
        python: str | Path = sys.executable,
        data_dir: str | Path | None = None,
        now: datetime | None = None,
    ) -> None:
        self.home = Path(home).expanduser() if home else Path.home()
        self.python = str(Path(python).expanduser())
        self.data_dir = (
            Path(data_dir).expanduser()
            if data_dir
            else self.home / ".jobfindsme" / "data"
        )
        self.now = now or datetime.now(UTC)
        self.skill_content = (
            files("jobfindsme.resources.jobfindsme")
            .joinpath("SKILL.md")
            .read_text(encoding="utf-8")
        )

    def install(self, host: str, *, config_path: Path | None = None) -> InstallResult:
        return self._write(
            host, replace=False, action="install", config_path=config_path
        )  # noqa: E501

    def upgrade(self, host: str, *, config_path: Path | None = None) -> InstallResult:
        return self._write(
            host, replace=True, action="upgrade", config_path=config_path
        )  # noqa: E501

    def connect(self, host: str, *, config_path: Path | None = None) -> InstallResult:
        """Idempotently connect jobfindsme to an Agent host."""

        return self._write(
            host, replace=True, action="connect", config_path=config_path
        )

    def uninstall(self, host: str, *, config_path: Path | None = None) -> InstallResult:
        if host == "generic":
            if not config_path:
                raise ValueError("--path is required for generic host")
            backup = self._backup(config_path) if config_path.exists() else None
            document = (
                json.loads(config_path.read_text()) if config_path.exists() else {}
            )  # noqa: E501
            document.get("mcpServers", {}).pop("jobfindsme", None)
            config_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return InstallResult(
                host="generic",
                action="uninstall",
                config_path=str(config_path),
                skill_path="",
                backups=(str(backup),) if backup else (),
            )
        self._validate_host(host)
        config_path, skill_path = self._paths(host)
        if not config_path.exists():
            raise FileNotFoundError(f"{host} config does not exist")
        backup = self._backup(config_path)
        if host == "codex":
            content = _remove_codex_config(config_path.read_text())
            config_path.write_text(content, encoding="utf-8")
        elif host == "zcode":
            document = json.loads(config_path.read_text())
            document.get("mcp", {}).get("servers", {}).pop("jobfindsme", None)
            config_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        elif host in _STANDARD_JSON_HOSTS:
            document = json.loads(config_path.read_text())
            document.get("mcpServers", {}).pop("jobfindsme", None)
            config_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        skill_path.unlink(missing_ok=True)
        return InstallResult(
            host=host,
            action="uninstall",
            config_path=str(config_path),
            skill_path=str(skill_path),
            backups=(str(backup),),
        )

    def _write(
        self, host: str, *, replace: bool, action: str, config_path: Path | None = None
    ) -> InstallResult:  # noqa: E501
        if host == "generic":
            if not config_path:
                raise ValueError("--path is required for generic host")
            self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            backup = self._backup(config_path) if config_path.exists() else None
            document = (
                json.loads(config_path.read_text()) if config_path.exists() else {}
            )  # noqa: E501
            servers = document.setdefault("mcpServers", {})
            if "jobfindsme" in servers and not replace:
                if backup:
                    backup.unlink()
                raise FileExistsError("jobfindsme MCP config already exists")
            servers["jobfindsme"] = self._json_server()
            config_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return InstallResult(
                host="generic",
                action=action,
                config_path=str(config_path),
                skill_path="",
                backups=(str(backup),) if backup else (),
            )
        self._validate_host(host)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        config_path, skill_path = self._paths(host)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        backup = self._backup(config_path) if config_path.exists() else None

        if host == "codex":
            existing = config_path.read_text() if config_path.exists() else ""
            marker = "[mcp_servers.jobfindsme]"
            if marker in existing and not replace:
                if backup:
                    backup.unlink()
                raise FileExistsError("Codex jobfindsme MCP config already exists")
            if replace:
                existing = _remove_codex_config(existing)
            config_path.write_text(
                existing.rstrip() + self._codex_block() + "\n",
                encoding="utf-8",
            )
        elif host == "zcode":
            document = (
                json.loads(config_path.read_text()) if config_path.exists() else {}
            )
            mcp = document.setdefault("mcp", {})
            servers = mcp.setdefault("servers", {})
            if "jobfindsme" in servers and not replace:
                if backup:
                    backup.unlink()
                raise FileExistsError("ZCode jobfindsme MCP config already exists")
            servers["jobfindsme"] = self._json_server()
            config_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        elif host in _STANDARD_JSON_HOSTS:
            document = (
                json.loads(config_path.read_text()) if config_path.exists() else {}
            )
            servers = document.setdefault("mcpServers", {})
            if "jobfindsme" in servers and not replace:
                if backup:
                    backup.unlink()
                raise FileExistsError(f"{host} jobfindsme MCP config already exists")
            servers["jobfindsme"] = self._json_server()
            config_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        self._install_skill(skill_path)
        return InstallResult(
            host=host,
            action=action,
            config_path=str(config_path),
            skill_path=str(skill_path),
            backups=(str(backup),) if backup else (),
            commands=(f"{host} mcp list",),
        )

    def _codex_block(self) -> str:
        return (
            "\n[mcp_servers.jobfindsme]\n"
            f"command = {json.dumps(self.python, ensure_ascii=False)}\n"
            'args = ["-m", "jobfindsme.mcp"]\n'
            "required = true\n"
            'default_tools_approval_mode = "prompt"\n'
            "\n[mcp_servers.jobfindsme.env]\n"
            f"JOBFINDSME_DB_PATH = "
            f"{json.dumps(str(self.data_dir / 'jobfindsme.db'), ensure_ascii=False)}\n"
        )

    def _json_server(self) -> dict[str, object]:
        return {
            "type": "stdio",
            "command": self.python,
            "args": ["-m", "jobfindsme.mcp"],
            "env": {
                "JOBFINDSME_DB_PATH": str(self.data_dir / "jobfindsme.db"),
            },
        }

    def _paths(self, host: str) -> tuple[Path, Path]:
        if host == "codex":
            return (
                self.home / ".codex" / "config.toml",
                self.home / ".codex" / "skills" / "jobfindsme" / "SKILL.md",
            )
        if host == "zcode":
            return (
                self.home / ".zcode" / "cli" / "config.json",
                self.home / ".zcode" / "skills" / "jobfindsme" / "SKILL.md",
            )
        if host in _STANDARD_JSON_HOSTS:
            cfg_rel, skill_rel = _STANDARD_JSON_HOSTS[host]
            return (
                self.home / cfg_rel,
                self.home / skill_rel / "jobfindsme" / "SKILL.md",
            )
        raise ValueError(f"unsupported host: {host}")

    def _install_skill(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.skill_content, encoding="utf-8")

    def _backup(self, path: Path) -> Path:
        timestamp = self.now.strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.name}.backup-{timestamp}")
        suffix = 1
        while backup.exists():
            backup = path.with_name(f"{path.name}.backup-{timestamp}.{suffix}")
            suffix += 1
        shutil.copy2(path, backup)
        return backup

    def _validate_host(self, host: str) -> None:
        if host not in self.HOSTS:
            raise ValueError(f"unsupported host: {host}")


def _remove_codex_config(content: str) -> str:
    lines = content.splitlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[mcp_servers.jobfindsme"):
            skipping = True
            continue
        if skipping and stripped.startswith("["):
            skipping = False
        if not skipping:
            kept.append(line)
    return "\n".join(kept).rstrip() + ("\n" if kept else "")
