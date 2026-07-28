from __future__ import annotations

import os
import shutil
import stat
import sys
from importlib.util import find_spec
from pathlib import Path

from jobfindsme.contracts import StrictModel
from jobfindsme.core import JobFindsMeCore
from jobfindsme.mcp.server import StdioMcpServer
from jobfindsme.mcp.tools import ToolRegistry


def _browser_binary_available() -> bool:
    system_browsers = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    )
    if any(Path(path).is_file() for path in system_browsers):
        return True
    if any(
        shutil.which(command)
        for command in (
            "google-chrome",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
        )
    ):
        return True
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).is_file()
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
            from jobfindsme.connectors import (
                AshbyConnector,
                BaiduCareerConnector,
                GreenhouseConnector,
                JsonLdCareerSiteConnector,
            )

            names = (
                AshbyConnector.__name__,
                BaiduCareerConnector.__name__,
                GreenhouseConnector.__name__,
                JsonLdCareerSiteConnector.__name__,
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
            "playwright": "playwright",
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
                    '"jobfindsme[browser]" and Playwright Chromium'
                ),
            )
        if not _browser_binary_available():
            return Diagnostic(
                name="browser_connectors",
                ok=False,
                required=False,
                message=(
                    "optional packages are installed but no compatible browser "
                    "was found; run 'python -m playwright install chromium'"
                ),
            )
        return Diagnostic(
            name="browser_connectors",
            ok=True,
            required=False,
            message=(
                "optional packages and a compatible browser are ready; "
                "BOSS additionally requires an explicit local CDP session"
            ),
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
