from __future__ import annotations

import os
import stat
import sys
from importlib.util import find_spec
from pathlib import Path

from jobfindsme.contracts import StrictModel
from jobfindsme.core import JobFindsMeCore
from jobfindsme.mcp.server import StdioMcpServer
from jobfindsme.mcp.tools import ToolRegistry


import urllib.request


def _cdp_port_reachable() -> bool:
    """Check if Chrome DevTools Protocol is available on port 9222."""
    try:
        req = urllib.request.Request("http://127.0.0.1:9222/json/version")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


class Diagnostic(StrictModel):
    name: str
    ok: bool
    message: str
    required: bool = True


class DoctorReport(StrictModel):
    ok: bool
    diagnostics: tuple[Diagnostic, ...]


class Doctor:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser()

    def run(self) -> DoctorReport:
        diagnostics = (
            self._version(),
            self._python(),
            self._database(),
            self._permissions(),
            self._mcp(),
            self._connectors(),
            self._browser_connectors(),
            self._secrets(),
        )
        return DoctorReport(
            ok=all(item.ok or not item.required for item in diagnostics),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _version() -> Diagnostic:
        try:
            from importlib.metadata import version

            v = version("jobfindsme")
        except Exception:
            v = "unknown"
        return Diagnostic(
            name="version",
            ok=True,
            message=f"jobfindsme {v}  |  更新: jobfindsme self-update",
        )

    @staticmethod
    def _python() -> Diagnostic:
        ok = sys.version_info >= (3, 11)
        return Diagnostic(
            name="python",
            ok=ok,
            message=f"Python {sys.version_info.major}.{sys.version_info.minor}",
        )

    def _database(self) -> Diagnostic:
        try:
            core = JobFindsMeCore(self.database_path)
            with core.database.connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except Exception as error:
            return Diagnostic(name="database", ok=False, message=str(error))
        return Diagnostic(name="database", ok=True, message=str(self.database_path))

    def _permissions(self) -> Diagnostic:
        directory = self.database_path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        mode = stat.S_IMODE(directory.stat().st_mode)
        ok = mode & 0o077 == 0
        return Diagnostic(
            name="permissions",
            ok=ok,
            message=f"{directory} mode={mode:o}",
        )

    def _mcp(self) -> Diagnostic:
        try:
            core = JobFindsMeCore(self.database_path)
            response = StdioMcpServer(ToolRegistry(core)).handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                }
            )
            count = len(response["result"]["tools"])
        except Exception as error:
            return Diagnostic(name="mcp", ok=False, message=str(error))
        return Diagnostic(name="mcp", ok=count == 9, message=f"{count} tools")

    @staticmethod
    def _connectors() -> Diagnostic:
        try:
            from jobfindsme.connectors.boss_zhipin import BossZhipinConnector
            from jobfindsme.connectors.china_platforms import (
                LagouConnector,
                LiepinConnector,
                ZhilianConnector,
            )

            names = (
                BossZhipinConnector.__name__,
                LiepinConnector.__name__,
                ZhilianConnector.__name__,
                LagouConnector.__name__,
            )
        except ImportError as error:
            return Diagnostic(name="connectors", ok=False, message=str(error))
        return Diagnostic(
            name="connectors",
            ok=True,
            message=f"ready: {', '.join(names)}",
        )

    @staticmethod
    def _browser_connectors() -> Diagnostic:
        modules = {
            "requests": "requests",
            "websocket-client": "websocket",
        }
        missing = [
            label for label, module in modules.items() if find_spec(module) is None
        ]
        if missing:
            return Diagnostic(
                name="browser_connectors",
                ok=False,
                required=False,
                message=(
                    f"optional unavailable: {', '.join(missing)}; install "
                    '"jobfindsme[browser]"'
                ),
            )
        cdp_available = _cdp_port_reachable()
        if not cdp_available:
            return Diagnostic(
                name="browser_connectors",
                ok=False,
                required=False,
                message=(
                    "Chrome CDP (port 9222) not reachable — run "
                    "'jobfindsme setup' to launch Chrome for BOSS/猎聘/智联/拉勾"
                ),
            )
        return Diagnostic(
            name="browser_connectors",
            ok=True,
            required=False,
            message="Chrome CDP available on port 9222; platform search is ready",
        )

    @staticmethod
    def _secrets() -> Diagnostic:
        configured = [name for name in ("FEISHU_WEBHOOK_URL",) if os.getenv(name)]
        return Diagnostic(
            name="secrets",
            ok=True,
            message=(
                f"optional configured: {', '.join(configured)}"
                if configured
                else "no optional secrets configured"
            ),
        )
