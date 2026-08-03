"""Tests for the pure-HTTP 前程无忧 connector."""

from __future__ import annotations

from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.wuyou import WuyouBlockedError, WuyouHttpConnector


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
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.get_urls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_urls.append(url)
        return self._response


def _item() -> dict[str, Any]:
    return {
        "jobid": "123456",
        "job_name": "AI应用工程师",
        "company_name": "示例科技",
        "workarea_text": "上海-浦东新区",
        "providesalary_text": "20-40K·14薪",
        "issue_date": "2026-08-01",
        "jobwelf": "五险一金",
        "job_href": "/job_search/example.html",
        "jobtype_text": "全职",
    }


def test_wuyou_parses_job_payload() -> None:
    payload = {"status": "1", "resultbody": {"job": {"items": [_item()]}}}
    session = FakeSession(
        FakeResponse(
            json_data=payload,
            text='{"status":"1"}',
            headers={"Content-Type": "application/json"},
        )
    )
    connector = WuyouHttpConnector(
        "AI应用工程师",
        city="上海",
        policy=_policy(),
        session_factory=lambda: session,
    )

    records = connector.fetch()

    assert len(records) == 1
    record = records[0]
    assert record.payload["title"] == "AI应用工程师"
    assert record.payload["company"] == "示例科技"
    assert record.payload["salary"] == "20-40K·14薪"
    assert (
        record.payload["apply_url"] == "https://www.51job.com/job_search/example.html"
    )
    assert record.payload["employment_type"] == "full_time"
    assert "we.51job.com/api/job/search-pc" in session.get_urls[0]


def test_wuyou_waf_challenge_raises_blocked() -> None:
    session = FakeSession(
        FakeResponse(
            text='<textarea id="renderData">{"_waf_bd8ce2ce37":"..."}</textarea>'
            '<meta name="aliyun_waf_aa" content="...">',
            headers={"Content-Type": "text/html"},
        )
    )
    connector = WuyouHttpConnector(
        "AI应用工程师",
        policy=_policy(),
        session_factory=lambda: session,
    )

    with pytest.raises(WuyouBlockedError, match="安全校验"):
        connector.fetch()


def test_wuyou_empty_items_returns_empty() -> None:
    payload = {"status": "1", "resultbody": {"job": {"items": []}}}
    session = FakeSession(
        FakeResponse(
            json_data=payload,
            text='{"status":"1"}',
            headers={"Content-Type": "application/json"},
        )
    )
    connector = WuyouHttpConnector(
        "AI应用工程师",
        policy=_policy(),
        session_factory=lambda: session,
    )

    assert connector.fetch() == []
