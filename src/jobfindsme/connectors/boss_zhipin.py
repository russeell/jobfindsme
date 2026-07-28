"""BOSS直聘 connector via Chrome CDP.

Connects to a locally running Chrome with remote debugging enabled,
calls BOSS's internal search API from within the user's logged-in
browser session, and extracts structured job records.

Based on the boss-zhipin-scraper project by eatmoreduck (MIT).
https://github.com/eatmoreduck/boss-zhipin-scraper

Requirements:
    pip install websocket-client requests
    Chrome must be running with: --remote-debugging-port=9222
    User must be logged into zhipin.com in that Chrome.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.contracts import SourceKind

BOSS_API_PATH = "/wapi/zpgeek/search/joblist.json"
DEFAULT_CDP_PORT = 9222

_JS_FETCH_API = """
(function(){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '__API_URL__', false);
    xhr.send();
    if (xhr.status !== 200) return JSON.stringify([{error: xhr.status}]);
    var data = JSON.parse(xhr.responseText);
    var jobs = (data.zpData || {}).jobList || [];
    return JSON.stringify(jobs.map(function(j) {
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
    }));
})()
"""


class _CDPSession:
    """Minimal Chrome DevTools Protocol session over WebSocket."""

    def __init__(self, port: int = DEFAULT_CDP_PORT) -> None:
        import requests  # optional dependency
        from websocket import create_connection  # optional dependency

        resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=10)
        ws_url = resp.json()["webSocketDebuggerUrl"]
        self.ws = create_connection(ws_url, timeout=60)
        self._mid = 0

    def send(
        self, method: str, params: dict | None = None, sid: str | None = None
    ) -> dict:
        self._mid += 1
        msg: dict = {"id": self._mid, "method": method, "params": params or {}}
        if sid:
            msg["sessionId"] = sid
        self.ws.send(json.dumps(msg))

        while True:
            raw = self.ws.recv()
            r = json.loads(raw)
            if r.get("id") == self._mid:
                return r

    def eval_js(self, js: str, sid: str) -> Any:
        r = self.send(
            "Runtime.evaluate",
            {"expression": js, "returnByValue": True},
            sid,
        )
        result = r.get("result", {}).get("result", {})
        return result.get("value")

    def close(self) -> None:
        self.ws.close()


class BossZhipinConnector:
    """Discover jobs from BOSS直聘 via Chrome CDP + internal search API."""

    def __init__(
        self,
        keyword: str,
        city: str = "",
        *,
        policy: ConnectorPolicy,
        source_name: str = "BOSS直聘",
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        self.keyword = keyword.strip()
        if not self.keyword or len(self.keyword) > 100:
            raise ValueError("invalid keyword")
        self.city = city.strip()
        self.source_name = source_name
        self.cdp_port = cdp_port

    def fetch(self) -> list[RawJobRecord]:
        cdp = _CDPSession(self.cdp_port)

        # Create a background page and attach
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

        # Override visibility so BOSS doesn't detect background tab
        cdp.send(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "Object.defineProperty(document,'hidden',{get:()=>false});"
                    "Object.defineProperty(document,'visibilityState',{get:()=>'visible'});"
                )
            },
            session_id,
        )

        # Build API URL
        params: dict[str, str | int] = {
            "query": self.keyword,
            "page": 1,
            "pageSize": 30,
        }
        if self.city:
            params["city"] = self.city
        api_url = f"{BOSS_API_PATH}?{urlencode(params)}"

        # Execute the API call via injected JS
        js = _JS_FETCH_API.replace("__API_URL__", api_url)
        raw = cdp.eval_js(js, session_id)
        cdp.close()

        if not isinstance(raw, str):
            return []
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if (
            not isinstance(items, list)
            or len(items) == 1
            and isinstance(items[0], dict)
            and "error" in items[0]
        ):
            return []

        source_url = f"https://www.zhipin.com/web/geek/job?query={self.keyword}"
        return [
            self._to_record(item, source_url)
            for item in items
            if isinstance(item, dict) and item.get("job_id")
        ]

    def _to_record(self, item: dict[str, Any], source_url: str) -> RawJobRecord:
        return RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name=self.source_name,
            source_url=source_url,
            external_id=item["job_id"],
            payload={
                "title": item.get("title", ""),
                "company": item.get("company", ""),
                "description": "",
                "location": item.get("location", ""),
                "salary": item.get("salary", ""),
                "experience": item.get("experience", ""),
                "degree": item.get("degree", ""),
                "skills": item.get("skills", ""),
                "url": item.get("job_link", source_url),
                "apply_url": item.get("job_link", source_url),
                "boss_name": item.get("boss_name", ""),
                "boss_active": item.get("boss_active", ""),
                "company_scale": item.get("company_scale", ""),
                "company_stage": item.get("company_stage", ""),
                "welfare": item.get("welfare", ""),
            },
        )
