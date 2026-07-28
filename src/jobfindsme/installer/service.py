from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from jobfindsme.contracts import StrictModel


class InstallResult(StrictModel):
    host: str
    config_path: str
    skill_path: str
    backups: tuple[str, ...] = ()
    commands: tuple[str, ...] = Field(default_factory=tuple)


class HostInstaller:
    HOSTS = {"codex", "claude", "qwen"}

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
        self.skill_source = (
            Path(__file__).parents[3] / "integrations" / "shared" / "SKILL.md"
        )

    def install(self, host: str) -> InstallResult:
        if host not in self.HOSTS:
            raise ValueError(f"unsupported host: {host}")
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if host == "codex":
            return self._install_codex()
        if host == "claude":
            return self._install_json_host(
                host="claude",
                config_path=self.home / ".claude.json",
                skill_path=self.home / ".claude" / "skills" / "jobfindsme" / "SKILL.md",
            )
        return self._install_json_host(
            host="qwen",
            config_path=self.home / ".qwen" / "settings.json",
            skill_path=self.home / ".qwen" / "skills" / "jobfindsme" / "SKILL.md",
        )

    def _install_codex(self) -> InstallResult:
        config_path = self.home / ".codex" / "config.toml"
        skill_path = self.home / ".codex" / "skills" / "jobfindsme" / "SKILL.md"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing = config_path.read_text() if config_path.exists() else ""
        marker = "[mcp_servers.jobfindsme]"
        if marker in existing:
            raise FileExistsError("Codex jobfindsme MCP config already exists")
        backup = self._backup(config_path)
        block = (
            "\n[mcp_servers.jobfindsme]\n"
            f"command = {json.dumps(self.python)}\n"
            'args = ["-m", "jobfindsme.mcp"]\n'
            "required = true\n"
            'default_tools_approval_mode = "prompt"\n'
            "\n[mcp_servers.jobfindsme.env]\n"
            f"JOBFINDSME_DB_PATH = {json.dumps(str(self.data_dir / 'jobfindsme.db'))}\n"
        )
        config_path.write_text(existing.rstrip() + block + "\n")
        self._install_skill(skill_path)
        return InstallResult(
            host="codex",
            config_path=str(config_path),
            skill_path=str(skill_path),
            backups=(str(backup),) if backup else (),
            commands=("codex mcp list",),
        )

    def _install_json_host(
        self,
        *,
        host: str,
        config_path: Path,
        skill_path: Path,
    ) -> InstallResult:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        document = json.loads(config_path.read_text()) if config_path.exists() else {}
        servers = document.setdefault("mcpServers", {})
        if "jobfindsme" in servers:
            raise FileExistsError(f"{host} jobfindsme MCP config already exists")
        backup = self._backup(config_path)
        server = {
            "command": self.python,
            "args": ["-m", "jobfindsme.mcp"],
            "env": {
                "JOBFINDSME_DB_PATH": str(self.data_dir / "jobfindsme.db"),
            },
        }
        if host == "claude":
            server["type"] = "stdio"
        servers["jobfindsme"] = server
        config_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        )
        self._install_skill(skill_path)
        return InstallResult(
            host=host,
            config_path=str(config_path),
            skill_path=str(skill_path),
            backups=(str(backup),) if backup else (),
            commands=(f"{host} mcp list",),
        )

    def _install_skill(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self._backup(target)
        shutil.copyfile(self.skill_source, target)

    def _backup(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        timestamp = self.now.strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.name}.backup-{timestamp}")
        if backup.exists():
            raise FileExistsError(f"backup already exists: {backup}")
        shutil.copy2(path, backup)
        return backup
