"""BOSS直聘 connector through a user-authorized local Chrome CDP session."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import urlencode

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.contracts import SourceKind

BOSS_ORIGIN = "https://www.zhipin.com"
BOSS_SEARCH_PAGE = f"{BOSS_ORIGIN}/web/geek/job"
BOSS_API_PATH = "/wapi/zpgeek/search/joblist.json"
DEFAULT_CDP_PORT = 9222

_JS_FETCH_API = """
(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '__API_URL__', false);
    xhr.withCredentials = true;
    xhr.send();
    if (xhr.status === 401 || xhr.status === 403) {
        return JSON.stringify({error: 'authentication_required', status: xhr.status});
    }
    if (xhr.status !== 200) {
        return JSON.stringify({error: 'http_error', status: xhr.status});
    }
    var data = JSON.parse(xhr.responseText);
    var jobs = (data.zpData || {}).jobList || [];
    return JSON.stringify({jobs: jobs.map(function(j) {
        return {
            job_id: j.encryptJobId || j.securityId || '',
            title: j.jobName || '',
            salary: j.salaryDesc || '',
            location: [j.cityName, j.areaDistrict, j.businessDistrict]
                .filter(function(v){return v && v !== '\\u4e0d\\u9650';}).join(' · '),
            company: j.brandName || '',
            experience: j.jobExperience || '',
            degree: j.jobDegree || '',
            skills: (j.skills || []).join(', '),
            job_labels: (j.jobLabels || []).join(', '),
            boss_name: j.bossTitle || '',
            boss_active: j.activeTimeDesc || (j.bossOnline ? '\\u5728\\u7ebf' : ''),
            company_scale: j.brandScaleName || '',
            company_stage: j.brandStageName || '',
            company_industry: j.brandIndustry || '',
            welfare: (j.welfareList || []).join(', '),
            job_link: j.encryptJobId
                ? 'https://www.zhipin.com/job_detail/' + j.encryptJobId + '.html'
                : ''
        };
    })});
})()
"""


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
    """Minimal Chrome DevTools Protocol session over a local WebSocket."""

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
                timeout=10,
            )
            response.raise_for_status()
            websocket_url = response.json()["webSocketDebuggerUrl"]
            self.ws = create_connection(
                websocket_url,
                timeout=60,
                origin=f"http://127.0.0.1:{port}",
            )
        except Exception as exc:
            raise BossConnectorError(
                f"无法连接 Chrome 调试端口 127.0.0.1:{port}。\n"
                "请先开启 Chrome 远程调试：\n"
                "  macOS: open -a 'Google Chrome' --args --remote-debugging-port=9222\n"
                "  Linux: google-chrome --remote-debugging-port=9222\n"
                f"然后在 Chrome 中打开 {BOSS_ORIGIN} 登录。"
            ) from exc
        self._message_id = 0

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        sid: str | None = None,
    ) -> dict[str, Any]:
        self._message_id += 1
        message: dict[str, Any] = {
            "id": self._message_id,
            "method": method,
            "params": params or {},
        }
        if sid:
            message["sessionId"] = sid
        self.ws.send(json.dumps(message))

        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") != self._message_id:
                continue
            if "error" in response:
                raise BossConnectorError(f"CDP {method} failed: {response['error']}")
            return response

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
                f"BOSS page JavaScript failed: {result.get('description', result)}"
            )
        return result.get("value")

    def close(self) -> None:
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
        self.city = city.strip()
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
                _JS_FETCH_API.replace("__API_URL__", api_url),
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
        timeout_seconds: float = 15,
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
                "recruitment_track": "social",
                "company_scale": item.get("company_scale", ""),
                "company_stage": item.get("company_stage", ""),
                "company_industry": item.get("company_industry", ""),
                "welfare": item.get("welfare", ""),
            },
        )
