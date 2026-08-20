"""BOSS直聘 connector through a user-authorized local Chrome CDP session."""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Callable
from contextlib import suppress
from importlib.resources import files
from typing import Any, Protocol
from urllib.parse import urlencode

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.contracts import SourceKind

BOSS_ORIGIN = "https://www.zhipin.com"
BOSS_SEARCH_PAGE = f"{BOSS_ORIGIN}/web/geek/job"
BOSS_API_PATH = "/wapi/zpgeek/search/joblist.json"
DEFAULT_CDP_PORT = 9222
BOSS_CITY_CODES = {
    "北京": "101010100",
    "上海": "101020100",
    "重庆": "101040100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "南京": "101190100",
    "苏州": "101190400",
    "武汉": "101200100",
    "成都": "101270100",
    "西安": "101110100",
}

_JS_FETCH_API = (
    files("jobfindsme.resources.connectors")
    .joinpath("boss_fetch.js")
    .read_text(encoding="utf-8")
)


class BossConnectorError(RuntimeError):
    """Base failure for an unavailable or invalid BOSS browser bridge."""


class BossAuthenticationRequired(BossConnectorError):
    """The attached browser has no usable BOSS login session."""


class CdpSession(Protocol):
    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        sid: str | None = None,
    ) -> dict[str, Any]: ...

    def eval_js(self, js: str, sid: str) -> Any: ...

    def close(self) -> None: ...


class _CDPSession:
    """Chrome DevTools Protocol session with read/write separation.

    A background reader thread continuously receives CDP messages and
    routes them: responses (with ``id``) resolve pending futures, and
    events (with ``method``) are pushed into a thread-safe queue for
    interception by callers (e.g. Network.responseReceived).

    This fixes the bug where ``send()`` would consume and discard
    unsolicited CDP events while waiting for its own response.
    """

    @staticmethod
    def minimize_windows(port: int = DEFAULT_CDP_PORT) -> None:
        """Hide all Chrome windows so search tabs don't visibly pop up."""
        with suppress(Exception):
            cdp = _CDPSession(port)
            targets = cdp.send("Target.getTargets")
            bounds = {"windowState": "minimized"}
            for t in targets.get("result", {}).get("targetInfos", []):
                if t.get("type") == "page":
                    with suppress(Exception):
                        window = cdp.send(
                            "Browser.getWindowForTarget",
                            {"targetId": t["targetId"]},
                        )
                        window_id = window["result"]["windowId"]
                        cdp.send(
                            "Browser.setWindowBounds",
                            {"windowId": window_id, "bounds": bounds},
                        )
            cdp.close()

    def __init__(self, port: int = DEFAULT_CDP_PORT) -> None:
        try:
            import requests
            from websocket import create_connection
        except ImportError as exc:
            raise BossConnectorError(
                'BOSS requires the "jobfindsme[browser]" optional dependencies.'
            ) from exc

        try:
            response = requests.get(
                f"http://127.0.0.1:{port}/json/version",
                timeout=3,
            )
            response.raise_for_status()
            websocket_url = response.json()["webSocketDebuggerUrl"]
            self.ws = create_connection(
                websocket_url,
                timeout=15,
                origin=f"http://127.0.0.1:{port}",
            )
        except (OSError, ValueError, TimeoutError) as exc:
            raise BossConnectorError(
                f"无法连接 Chrome 调试端口 127.0.0.1:{port}。\n"
                "请先开启 Chrome 远程调试：\n"
                "  macOS: open -a 'Google Chrome' --args --remote-debugging-port=9222\n"
                "  Linux: google-chrome --remote-debugging-port=9222\n"
                f"然后在 Chrome 中打开 {BOSS_ORIGIN} 登录。"
            ) from exc
        self._message_id = 0
        self._lock = __import__("threading").Lock()
        self._futures: dict[int, __import__("threading").Event] = {}
        self._results: dict[int, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._running = True
        self._reader = __import__("threading").Thread(
            target=self._read_loop, daemon=True
        )
        self._reader.start()

    def _read_loop(self) -> None:
        """Continuously read CDP messages and dispatch by type."""
        while self._running:
            try:
                raw = self.ws.recv()
            except Exception:
                if self._running:
                    time.sleep(0.1)
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_id = msg.get("id")
            with self._lock:
                if msg_id is not None:
                    self._results[msg_id] = msg
                    future = self._futures.pop(msg_id, None)
                    if future:
                        future.set()
                elif msg.get("method"):
                    self._events.append(msg)

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        sid: str | None = None,
    ) -> dict[str, Any]:
        self._message_id += 1
        mid = self._message_id
        message: dict[str, Any] = {
            "id": mid,
            "method": method,
            "params": params or {},
        }
        if sid:
            message["sessionId"] = sid

        event = __import__("threading").Event()
        with self._lock:
            self._futures[mid] = event
        self.ws.send(json.dumps(message))

        if not event.wait(timeout=12):
            raise BossConnectorError(f"CDP {method} timed out after 12s")
        with self._lock:
            response = self._results.pop(mid, None)
        if response is None:
            raise BossConnectorError(f"CDP {method} returned no response")
        if "error" in response:
            raise BossConnectorError(f"CDP {method} failed: {response['error']}")
        return response

    def drain_events(self) -> list[dict[str, Any]]:
        """Return and clear all buffered CDP events (non-response messages)."""
        with self._lock:
            events = self._events
            self._events = []
            return events

    def eval_js(self, js: str, sid: str) -> Any:
        response = self.send(
            "Runtime.evaluate",
            {
                "expression": js,
                "returnByValue": True,
                "awaitPromise": True,
            },
            sid,
        )
        result = response.get("result", {}).get("result", {})
        if result.get("subtype") == "error":
            raise BossConnectorError(
                f"JavaScript evaluation failed: {result.get('description', result)}"
            )
        return result.get("value")

    def close(self) -> None:
        self._running = False
        if self._reader.is_alive():
            self._reader.join(timeout=2)
        self.ws.close()


class BossZhipinConnector:
    """Discover jobs through the user's logged-in BOSS browser session."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "BOSS直聘",
        cdp_port: int = DEFAULT_CDP_PORT,
        session_factory: Callable[[int], CdpSession] = _CDPSession,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        if not self.keyword or len(self.keyword) > 100:
            raise ValueError("invalid keyword")
        normalized_city = city.strip()
        self.city = BOSS_CITY_CODES.get(normalized_city, normalized_city)
        self.source_name = source_name
        self.cdp_port = cdp_port
        self.session_factory = session_factory

    def fetch(self) -> list[RawJobRecord]:
        cdp = self.session_factory(self.cdp_port)
        target_id: str | None = None
        try:
            target = cdp.send(
                "Target.createTarget",
                {"url": "about:blank", "background": True},
            )
            target_id = target["result"]["targetId"]
            attached = cdp.send(
                "Target.attachToTarget",
                {"targetId": target_id, "flatten": True},
            )
            session_id = attached["result"]["sessionId"]
            cdp.send("Page.enable", sid=session_id)
            cdp.send("Runtime.enable", sid=session_id)
            cdp.send(
                "Page.navigate",
                {"url": BOSS_SEARCH_PAGE},
                session_id,
            )
            self._wait_until_ready(cdp, session_id)

            params: dict[str, str | int] = {
                "query": self.keyword,
                "page": 1,
                "pageSize": 30,
            }
            if self.city:
                params["city"] = self.city
            api_url = f"{BOSS_ORIGIN}{BOSS_API_PATH}?{urlencode(params)}"
            raw = cdp.eval_js(
                _JS_FETCH_API.replace("__API_URL__", json.dumps(api_url)),
                session_id,
            )
            items = self._parse_response(raw)
            source_url = f"{BOSS_SEARCH_PAGE}?{urlencode({'query': self.keyword})}"
            return [
                self._to_record(item, source_url)
                for item in items
                if item.get("job_id")
            ]
        finally:
            if target_id is not None:
                with suppress(Exception):
                    cdp.send("Target.closeTarget", {"targetId": target_id})
            cdp.close()

    @staticmethod
    def _wait_until_ready(
        cdp: CdpSession,
        session_id: str,
        *,
        timeout_seconds: float = 8,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if cdp.eval_js("document.readyState", session_id) in {
                "interactive",
                "complete",
            }:
                return
            time.sleep(0.1)
        raise BossConnectorError("BOSS page did not become ready before timeout")

    @staticmethod
    def _parse_response(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, str):
            raise BossConnectorError("BOSS returned no structured response")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BossConnectorError("BOSS returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise BossConnectorError("BOSS returned an invalid response envelope")
        if payload.get("error") == "authentication_required":
            raise BossAuthenticationRequired(
                "Log in to BOSS in the dedicated Chrome profile and retry."
            )
        if payload.get("error"):
            raise BossConnectorError(
                f"BOSS search failed: {payload['error']} "
                f"(status={payload.get('status')})"
            )
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise BossConnectorError("BOSS response is missing the jobs list")
        return [item for item in jobs if isinstance(item, dict)]

    def _to_record(
        self,
        item: dict[str, Any],
        source_url: str,
    ) -> RawJobRecord:
        classification_text = " ".join(
            str(item.get(key, "")) for key in ("title", "job_labels")
        ).casefold()
        recruitment_track = (
            "campus"
            if any(term in classification_text for term in ("校招", "校园", "应届"))
            else "social"
        )
        if any(term in classification_text for term in ("实习", "intern")):
            employment_type = "internship"
        elif "兼职" in classification_text:
            employment_type = "part_time"
        elif "合同" in classification_text:
            employment_type = "contract"
        else:
            employment_type = "full_time"
        return RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name=self.source_name,
            source_url=source_url,
            external_id=str(item["job_id"]),
            payload={
                "title": item.get("title", ""),
                "company": item.get("company", ""),
                "description": " ".join(
                    value
                    for value in (
                        str(item.get("skills", "")).strip(),
                        str(item.get("job_labels", "")).strip(),
                        str(item.get("welfare", "")).strip(),
                    )
                    if value
                ),
                "location": item.get("location", ""),
                "salary": item.get("salary", ""),
                "experience": item.get("experience", ""),
                "degree": item.get("degree", ""),
                "skills": item.get("skills", ""),
                "url": item.get("job_link", source_url),
                "apply_url": item.get("job_link", source_url),
                "boss_name": item.get("boss_name", ""),
                "boss_active": item.get("boss_active", ""),
                "recruitment_track": recruitment_track,
                "employment_type": employment_type,
                "company_scale": item.get("company_scale", ""),
                "company_stage": item.get("company_stage", ""),
                "company_industry": item.get("company_industry", ""),
                "welfare": item.get("welfare", ""),
            },
        )


# ── Chrome profile management ────────────────────────────────────────────────

BOSS_PROFILE_DIR = "~/.jobfindsme/chrome-profile"

PLATFORM_LOGIN_URLS = {
    "boss": ("https://www.zhipin.com/web/user/", "BOSS直聘"),
    "liepin": ("https://www.liepin.com/login/", "猎聘"),
}


def _chrome_command(chrome: str, profile: str, urls: list[str]) -> list[str]:
    """Build the isolated browser command without weakening Chrome's sandbox."""
    return [
        chrome,
        f"--remote-debugging-port={DEFAULT_CDP_PORT}",
        "--remote-allow-origins=http://127.0.0.1:9222",
        f"--user-data-dir={profile}",
        *urls,
    ]


def _cdp_reachable(
    port: int = DEFAULT_CDP_PORT,
    timeout: float = 1.0,
) -> bool:
    """True when the local Chrome CDP bridge is already listening."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def setup_chrome(platforms: tuple[str, ...] = ()) -> dict:
    """Launch an isolated Chrome profile for platform login.

    Opens the login page for each selected platform. The user logs in
    once per platform; sessions persist in ~/.jobfindsme/chrome-profile.

    If the CDP port is already reachable the bridge is already running —
    never launch a second instance (that would orphan the PID file).

    Args:
        platforms: Which platforms to open (boss, liepin).
                   If empty, opens BOSS only.
    """
    import subprocess
    from pathlib import Path

    profile = Path(BOSS_PROFILE_DIR).expanduser()
    profile.mkdir(parents=True, exist_ok=True)

    if _cdp_reachable():
        return {
            "ok": True,
            "message": (
                f"Chrome 已在运行（端口 {DEFAULT_CDP_PORT}）。\n"
                "直接在弹出的窗口扫码登录 BOSS直聘即可；\n"
                "如无窗口或需要重新登录，先运行 jobfindsme stop 再执行本命令。"
            ),
        }

    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe"
        ),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]

    chrome = next((p for p in chrome_paths if Path(p).exists()), None)
    if not chrome:
        return {
            "ok": False,
            "message": "未找到 Chrome。请安装 Google Chrome 后重试。",
        }

    selected = list(platforms) if platforms else ["boss"]
    if not all(p in PLATFORM_LOGIN_URLS for p in selected):
        return {
            "ok": False,
            "message": (
                f"不支持的平台：{set(selected) - set(PLATFORM_LOGIN_URLS)}\n"
                f"可选：{', '.join(PLATFORM_LOGIN_URLS)}"
            ),
        }

    urls = [PLATFORM_LOGIN_URLS[p][0] for p in selected]
    labels = [PLATFORM_LOGIN_URLS[p][1] for p in selected]

    proc = subprocess.Popen(
        _chrome_command(chrome, str(profile), urls),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Save PID so we can kill only this Chrome, not the user's own browser
    pid_file = profile / "chrome.pid"
    pid_file.write_text(str(proc.pid))
    label_list = "\n".join(f"  • {label}" for label in labels)
    return {
        "ok": True,
        "message": (
            f"Chrome 已启动（端口 {DEFAULT_CDP_PORT}）。\n"
            f"请在打开的窗口里登录以下平台：\n"
            f"{label_list}\n\n"
            "搜索期间请保持这个专用 Chrome 进程运行。\n"
            "登录态保存在本地，下次只需重新启动浏览器桥。\n"
            f"Profile: {profile}"
        ),
    }


def stop_chrome() -> dict:
    """Stop the isolated Chrome launched by ``setup_chrome``.

    Only kills the process recorded in ``chrome.pid`` — never touches
    the user's everyday Chrome windows.
    """
    import signal
    from pathlib import Path

    profile = Path(BOSS_PROFILE_DIR).expanduser()
    pid_file = profile / "chrome.pid"
    if not pid_file.is_file():
        return {
            "ok": False,
            "message": "chrome.pid not found — Chrome may not be running",
        }
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        return {"ok": True, "message": f"Chrome (PID {pid}) 已停止"}
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        return {"ok": True, "message": "Chrome 进程已经不存在"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
