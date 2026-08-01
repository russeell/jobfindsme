from __future__ import annotations

import json
from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.china_platforms import (
    CdpBlockedError,
    CdpFetchError,
    LiepinConnector,
    _cdp_fetch,
    _cdp_fetch_detail,
    _sanitize_external_id,
    enrich_job_descriptions,
)
from jobfindsme.contracts import SourceKind


def _policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


def test_platform_connector_maps_compact_job_records(
    monkeypatch: pytest.MonkeyPatch,
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
    records = LiepinConnector(
        "AI应用工程师",
        city="上海",
        policy=_policy(),
    ).fetch()

    assert len(records) == 1
    assert records[0].source_name == "猎聘"
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
                    "url": "https://www.zhaopin.com/security-check",
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
            "https://www.zhaopin.com/sou/",
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


class DetailCdp(FakeCdp):
    def eval_js(self, js: str, _sid: str) -> Any:
        if self.fail:
            raise RuntimeError("detail extraction failed")
        if js == "document.readyState":
            return "complete"
        if js == "document.body.innerText.length":
            return 1000
        return "岗位职责：负责 RAG 与 Agent 开发。任职要求：熟悉 Python。" * 5


def test_detail_fetch_returns_jd_and_closes_target() -> None:
    fake = DetailCdp()

    description = _cdp_fetch_detail(
        "https://jobs.example.com/detail/1",
        platform="liepin",
        session_factory=lambda _port: fake,
        dwell_seconds=0,
    )

    assert "岗位职责" in description
    assert fake.target_closed is True
    assert fake.closed is True


def test_detail_fetch_degrades_to_empty_and_still_closes_resources() -> None:
    fake = DetailCdp(fail=True)

    description = _cdp_fetch_detail(
        "https://jobs.example.com/detail/1",
        platform="liepin",
        session_factory=lambda _port: fake,
        dwell_seconds=0,
    )

    assert description == ""
    assert fake.target_closed is True
    assert fake.closed is True


def test_description_enrichment_is_bounded_and_preserves_provenance() -> None:
    records = [
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="猎聘",
            source_url="https://www.liepin.com/search",
            external_id=str(index),
            payload={
                "title": f"AI工程师{index}",
                "company": "示例科技",
                "url": f"https://www.liepin.com/job/{index}",
                "description": "",
            },
        )
        for index in range(5)
    ]
    calls = []

    def fetch_detail(url: str, **_kwargs: object) -> str:
        calls.append(url)
        return "岗位职责与任职要求 " * 20

    enriched = enrich_job_descriptions(
        records,
        platform="liepin",
        limit=2,
        detail_fetcher=fetch_detail,
    )

    assert len(calls) == 2
    assert enriched[0].payload["detail_level"] == "detail_page"
    assert enriched[0].payload["description_source_url"] == calls[0]
    assert enriched[2].payload["description"] == ""
