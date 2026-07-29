from __future__ import annotations

import os
import stat
import sys
import urllib.request
from importlib.util import find_spec
from pathlib import Path

from jobfindsme.contracts import StrictModel
from jobfindsme.core import jobfindsmecore
from jobfindsme.mcp.server import StdioMcpServer
from jobfindsme.mcp.tools import ToolRegistry


def _cdp_port_reachable() -> bool:
    """Check if Chrome DevTools Protocol is available on port 9222."""
    try:
        req = urllib.request.Request("http://127.0.0.1:9222/json/version")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


_BOSS_PROBE_JS = """
(function(){
    var x = new XMLHttpRequest();
    x.open('GET', '__API_URL__', false);
    try { x.send(); } catch(e) {}
    return x.responseText;
})()
"""


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
        return Diagnostic(name="mcp", ok=count == 9, message=f"{count} tools")

    @staticmethod
    def _connectors() -> Diagnostic:
        try:
            from jobfindsme.connectors.boss_zhipin import BossZhipinConnector
            from jobfindsme.connectors.china_platforms import (
                LagouConnector,
                LiepinConnector,
                WuyouConnector,
                ZhilianConnector,
            )

            names = (
                BossZhipinConnector.__name__,
                LiepinConnector.__name__,
                ZhilianConnector.__name__,
                LagouConnector.__name__,
                WuyouConnector.__name__,
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
            import json as _json
            from urllib.parse import urlencode

            from jobfindsme.connectors.boss_zhipin import (
                BOSS_API_PATH,
                BOSS_ORIGIN,
                DEFAULT_CDP_PORT,
                _CDPSession,
            )

            cdp = _CDPSession(DEFAULT_CDP_PORT)
            target = cdp.send(  # noqa: E501
                "Target.createTarget", {"url": "about:blank", "background": True}
            )
            target_id = target["result"]["targetId"]
            attached = cdp.send(  # noqa: E501
                "Target.attachToTarget",
                {"targetId": target_id, "flatten": True},
            )
            sid = attached["result"]["sessionId"]
            cdp.send("Page.enable", sid=sid)
            api_url = (
                f"{BOSS_ORIGIN}{BOSS_API_PATH}"
                f"?{urlencode({'query': '工程师', 'page': 1, 'pageSize': 1})}"
            )
            raw = cdp.eval_js(
                _BOSS_PROBE_JS.replace("__API_URL__", _json.dumps(api_url)), sid
            )
            cdp.send("Target.closeTarget", {"targetId": target_id})
            cdp.close()
            payload = _json.loads(raw) if isinstance(raw, str) else {}
            if payload.get("error") == "authentication_required":
                return Diagnostic(
                    name="boss_login",
                    ok=False,
                    required=False,
                    message=(
                        "BOSS直聘 requires login — run 'jobfindsme setup'. "
                        "Other 4 platforms work without login."
                    ),
                )
            job_count = len(payload.get("jobs", []))
            if job_count == 0:
                return Diagnostic(
                    name="boss_login",
                    ok=False,
                    required=False,
                    message=(
                        "BOSS直聘 returned 0 jobs — may need login. "
                        "Run 'jobfindsme setup'."
                    ),
                )
            return Diagnostic(
                name="boss_login",
                ok=True,
                required=False,
                message=f"BOSS直聘 — logged in, {job_count}+ jobs reachable",
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
