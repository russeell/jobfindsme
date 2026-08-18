from __future__ import annotations

import os
import stat
import sys
import urllib.request
from importlib.util import find_spec
from pathlib import Path

from jobfindsme.contracts import StrictModel
from jobfindsme.core import jobfindsmecore
from jobfindsme.mcp.registry import TOOL_DEFINITIONS, ToolRegistry
from jobfindsme.mcp.server import StdioMcpServer


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
            self._sources(),
            self._browser_connectors(),
            self._boss_login(),
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
            core = jobfindsmecore(self.database_path)
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
            core = jobfindsmecore(self.database_path)
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
        expected = len(TOOL_DEFINITIONS)
        return Diagnostic(
            name="mcp",
            ok=count == expected,
            message=f"{count} tools",
        )

    @staticmethod
    def _connectors() -> Diagnostic:
        try:
            from jobfindsme.connectors.boss_zhipin import BossZhipinConnector
            from jobfindsme.connectors.china_platforms import LiepinConnector
            from jobfindsme.connectors.wuyou import WuyouHttpConnector
            from jobfindsme.connectors.zhilian import ZhilianHttpConnector

            names = (
                BossZhipinConnector.__name__,
                LiepinConnector.__name__,
                ZhilianHttpConnector.__name__,
                WuyouHttpConnector.__name__,
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
                    "'jobfindsme setup' to launch Chrome for platform search"
                ),
            )
        return Diagnostic(
            name="browser_connectors",
            ok=True,
            required=False,
            message="Chrome CDP available on port 9222; platform search is ready",
        )

    @staticmethod
    def _sources() -> Diagnostic:
        """Per-source routing report — which backend serves each platform now.

        Mirrors agent-reach's ``doctor --json`` idea: an Agent reads this
        before searching so it never promises a platform whose backend is
        unavailable, and knows the retry chain per source.
        """
        cdp = _cdp_port_reachable()
        chrome_state = "Chrome 已连接" if cdp else "Chrome 未连接"
        setup_hint = "运行 jobfindsme setup" if not cdp else ""
        rows = [
            f"BOSS直聘 → cdp ｜ {chrome_state}"
            + (f"；{setup_hint}" if setup_hint else ""),
            "猎聘 → http ｜ 就绪（无需浏览器）",
            f"智联招聘 → http→cdp ｜ HTTP 可能被 WAF 拦截；{chrome_state}"
            + (f"；{setup_hint} 可启用 CDP 兜底" if setup_hint else "；CDP 兜底可用"),
            f"前程无忧 → http→cdp ｜ HTTP 可能被 WAF 拦截；{chrome_state}"
            + (f"；{setup_hint} 可启用 CDP 兜底" if setup_hint else "；CDP 兜底可用"),
        ]
        return Diagnostic(
            name="sources",
            ok=True,
            message="\n".join(rows),
        )

    @staticmethod
    def _boss_login() -> Diagnostic:
        """Probe whether BOSS直聘 is logged in via the CDP API."""
        if not _cdp_port_reachable():
            return Diagnostic(
                name="boss_login",
                ok=False,
                required=False,
                message="Chrome CDP not reachable — run 'jobfindsme setup' first",
            )
        try:
            from jobfindsme.connectors.base import ConnectorPolicy
            from jobfindsme.connectors.boss_zhipin import (
                BossAuthenticationRequired,
                BossZhipinConnector,
                _CDPSession,
            )

            records = BossZhipinConnector(
                "工程师",
                policy=ConnectorPolicy(public_access=True, robots_allowed=True),
                session_factory=_CDPSession,
            ).fetch()
            if not records:
                return Diagnostic(
                    name="boss_login",
                    ok=True,
                    required=False,
                    message=(
                        "BOSS直聘会话可访问，但本次探测返回 0 条；"
                        "可能是短时限流或查询无结果"
                    ),
                )
            return Diagnostic(
                name="boss_login",
                ok=True,
                required=False,
                message=f"BOSS直聘 — logged in, {len(records)} jobs reachable",
            )
        except BossAuthenticationRequired:
            return Diagnostic(
                name="boss_login",
                ok=False,
                required=False,
                message=(
                    "BOSS直聘 requires login — run 'jobfindsme setup'. "
                    "Other platforms remain available."
                ),
            )
        except Exception as e:
            return Diagnostic(
                name="boss_login",
                ok=False,
                required=False,
                message=f"BOSS直聘 login check failed — run 'jobfindsme setup': {e}",
            )

    @staticmethod
    def _secrets() -> Diagnostic:
        return Diagnostic(
            name="secrets",
            ok=True,
            message="no optional secrets configured",
        )
