from __future__ import annotations

import json
from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.china_platforms import (
    CdpBlockedError,
    CdpFetchError,
    LagouConnector,
    LiepinConnector,
    WuyouConnector,
    ZhilianConnector,
    _cdp_fetch,
    _sanitize_external_id,
)


def _policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


@pytest.mark.parametrize(
    ("connector_type", "source_name"),
    [
        (LiepinConnector, "猎聘"),
        (ZhilianConnector, "智联招聘"),
        (LagouConnector, "拉勾"),
        (WuyouConnector, "前程无忧"),
    ],
)
def test_platform_connector_maps_compact_job_records(
    monkeypatch: pytest.MonkeyPatch,
    connector_type,
    source_name: str,
) -> None:
    def fake_fetch(*_args, **_kwargs):
        return [
            {
                "title": "AI应用工程师",
                "company": "示例科技",
                "salary": "20-30K",
                "city": "上海",
                "url": "https://jobs.example.com/ai-1",
            }
        ]

    monkeypatch.setattr(
        "jobfindsme.connectors.china_platforms._cdp_fetch",
        fake_fetch,
    )
    records = connector_type(
        "AI应用工程师",
        city="上海",
        policy=_policy(),
    ).fetch()

    assert len(records) == 1
    assert records[0].source_name == source_name
    assert records[0].external_id == "https://jobs.example.com/ai-1"
    assert records[0].payload["title"] == "AI应用工程师"
    assert records[0].payload["apply_url"] == "https://jobs.example.com/ai-1"


class FakeCdp:
    def __init__(self, *, fail: bool = False, blocked: bool = False) -> None:
        self.fail = fail
        self.blocked = blocked
        self.target_closed = False
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
            self.target_closed = True
        return {"result": {}}

    def eval_js(self, js: str, _sid: str) -> Any:
        if self.fail:
            raise RuntimeError("DOM extraction failed")
        if js == "document.readyState":
            return "complete"
        if js == "document.body.innerText.length":
            return 1000
        if js.startswith("JSON.stringify({url:location.href"):
            return json.dumps(
                {
                    "url": "https://www.lagou.com/verify",
                    "title": "安全验证",
                    "text": "请完成滑动验证",
                }
            )
        if self.blocked:
            return "[]"
        return json.dumps([{"title": "AI应用工程师"}])

    def close(self) -> None:
        self.closed = True


def test_cdp_fetch_closes_background_target_and_session() -> None:
    fake = FakeCdp()

    jobs = _cdp_fetch(
        "https://jobs.example.com/search",
        "extract()",
        session_factory=lambda _port: fake,
        retries=0,
    )

    assert jobs == [{"title": "AI应用工程师"}]
    assert fake.target_closed is True
    assert fake.closed is True


def test_cdp_fetch_reports_extraction_failure_instead_of_empty_success() -> None:
    sessions: list[FakeCdp] = []

    def factory(_port: int) -> FakeCdp:
        session = FakeCdp(fail=True)
        sessions.append(session)
        return session

    with pytest.raises(CdpFetchError, match="after 2 attempts"):
        _cdp_fetch(
            "https://jobs.example.com/search",
            "extract()",
            session_factory=factory,
            retries=1,
        )

    assert len(sessions) == 2
    assert all(session.target_closed and session.closed for session in sessions)


def test_cdp_fetch_reports_risk_control_instead_of_empty_success() -> None:
    fake = FakeCdp(blocked=True)

    with pytest.raises(CdpBlockedError, match="滑动验证"):
        _cdp_fetch(
            "https://www.lagou.com/wn/jobs",
            "extract()",
            session_factory=lambda _port: fake,
            retries=0,
        )

    assert fake.target_closed is True
    assert fake.closed is True


def test_external_id_is_stable_and_avoids_long_url_prefix_collisions() -> None:
    tracked = "https://jobs.example.com/detail/42?tracking=" + "x" * 300
    assert _sanitize_external_id(tracked) == "https://jobs.example.com/detail/42"

    first = "https://jobs.example.com/?job=1&tracking=" + "x" * 300
    second = "https://jobs.example.com/?job=2&tracking=" + "x" * 300
    assert _sanitize_external_id(first) != _sanitize_external_id(second)
    assert len(_sanitize_external_id(first)) <= 256
