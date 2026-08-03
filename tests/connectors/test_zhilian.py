"""Tests for the pure-HTTP 智联招聘 connector."""

from __future__ import annotations

import json
from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.zhilian import (
    ZhilianBlockedError,
    ZhilianCdpConnector,
    ZhilianHttpConnector,
)


def _policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


class FakeResponse:
    def __init__(self, *, json_data: Any = None, text: str = "", headers=None) -> None:
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.status_code = 200

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("not json")
        return self._json_data


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.cookies = {}
        self._responses = list(responses)
        self.get_urls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_urls.append(url)
        if not self._responses:
            raise AssertionError("unexpected GET " + url)
        return self._responses.pop(0)


def _job() -> dict[str, Any]:
    return {
        "jobId": 12345,
        "jobName": "AI应用工程师（Agent方向）",
        "companyName": "示例科技",
        "city": {"display": "上海"},
        "salary": {"__value__": "20-40K·14薪"},
        "workingExp": {"name": "1-3年"},
        "eduLevel": {"name": "本科"},
        "jobType": {"name": "全职"},
        "positionURL": "https://www.zhaopin.com/job_detail/example.html",
        "welfare": ["五险一金", "弹性工作"],
        "companyType": {"name": "民营"},
    }


def test_zhilian_parses_job_payload() -> None:
    payload = {
        "code": 200,
        "apiCode": 200,
        "data": {"results": [_job()], "numTotal": 1},
    }
    session = FakeSession(
        [
            FakeResponse(
                text="<html>seed</html>", headers={"Content-Type": "text/html"}
            ),
            FakeResponse(
                json_data=payload,
                text="{}",
                headers={"Content-Type": "application/json"},
            ),
        ]
    )
    connector = ZhilianHttpConnector(
        "AI应用工程师",
        city="上海",
        policy=_policy(),
        session_factory=lambda: session,
    )

    records = connector.fetch()

    assert len(records) == 1
    record = records[0]
    assert record.payload["title"] == "AI应用工程师（Agent方向）"
    assert record.payload["company"] == "示例科技"
    assert record.payload["salary"] == "20-40K·14薪"
    assert record.payload["recruitment_track"] == "social"
    assert record.payload["employment_type"] == "full_time"
    assert (
        record.payload["apply_url"] == "https://www.zhaopin.com/job_detail/example.html"
    )
    assert "五险一金" in record.payload["welfare"]
    assert session.get_urls[0].startswith("https://sou.zhaopin.com/")
    assert "fe-api.zhaopin.com" in session.get_urls[1]


def test_zhilian_waf_challenge_raises_blocked() -> None:
    session = FakeSession(
        [
            FakeResponse(text="ok", headers={"Content-Type": "text/html"}),
            FakeResponse(
                text="<html>aliyun_waf challenge</html>",
                headers={"Content-Type": "text/html"},
            ),
        ]
    )
    connector = ZhilianHttpConnector(
        "AI应用工程师",
        policy=_policy(),
        session_factory=lambda: session,
    )

    with pytest.raises(ZhilianBlockedError):
        connector.fetch()


def test_zhilian_empty_envelope_raises_blocked() -> None:
    payload = {"code": 200, "apiCode": 200, "data": {"results": [], "numTotal": 0}}
    session = FakeSession(
        [
            FakeResponse(text="ok"),
            FakeResponse(
                json_data=payload,
                text="{}",
                headers={"Content-Type": "application/json"},
            ),
        ]
    )
    connector = ZhilianHttpConnector(
        "AI应用工程师",
        policy=_policy(),
        session_factory=lambda: session,
    )

    with pytest.raises(ZhilianBlockedError, match="风控"):
        connector.fetch()


class FakeCdp:
    def __init__(self, fetch_result: Any) -> None:
        self.fetch_result = fetch_result
        self.closed = False

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        sid: str | None = None,
    ) -> dict[str, Any]:
        if method == "Target.createTarget":
            return {"result": {"targetId": "target-1"}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": "session-1"}}
        if method == "Target.closeTarget":
            self.closed = True
        return {"result": {}}

    def eval_js(self, js: str, _sid: str) -> Any:
        if js == "document.readyState":
            return "complete"
        return self.fetch_result

    def close(self) -> None:
        self.closed = True


def test_zhilian_cdp_parses_job_payload() -> None:
    payload = {
        "code": 200,
        "apiCode": 200,
        "data": {"results": [_job()], "numTotal": 1},
    }
    cdp = FakeCdp(
        json.dumps({"ok": True, "text": json.dumps(payload, ensure_ascii=False)})
    )
    connector = ZhilianCdpConnector(
        "AI应用工程师",
        city="上海",
        policy=_policy(),
        session_factory=lambda _port: cdp,
        settle_seconds=0,
    )

    records = connector.fetch()

    assert len(records) == 1
    assert records[0].payload["company"] == "示例科技"
    assert (
        records[0].payload["apply_url"]
        == "https://www.zhaopin.com/job_detail/example.html"
    )
    assert cdp.closed


def test_zhilian_cdp_waf_blocked_raises() -> None:
    cdp = FakeCdp(json.dumps({"error": "waf_blocked", "status": 200}))
    connector = ZhilianCdpConnector(
        "AI应用工程师",
        policy=_policy(),
        session_factory=lambda _port: cdp,
        settle_seconds=0,
    )

    with pytest.raises(ZhilianBlockedError, match="页面内请求失败"):
        connector.fetch()
