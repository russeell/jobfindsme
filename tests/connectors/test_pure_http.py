"""Tests for the maintained pure-HTTP 猎聘 connector."""

from __future__ import annotations

from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.pure_http import (
    LiepinPureHttpConnector,
    PureHttpBlockedError,
)
from jobfindsme.contracts import SourceKind


def _policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


class FakeCookies(dict):
    def set(self, key: str, value: str, domain: str | None = None) -> None:
        self[key] = value


class FakeResponse:
    def __init__(
        self,
        *,
        json_data: Any = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.status_code = 200

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("not json")
        return self._json_data


class FakeSession:
    """Plays back queued GET/POST responses; can set cookies on demand."""

    def __init__(
        self,
        *,
        get_responses: list[FakeResponse] | None = None,
        post_responses: list[FakeResponse] | None = None,
        set_cookies_on_get: dict[str, str] | None = None,
    ) -> None:
        self.cookies = FakeCookies()
        self._gets = list(get_responses or [])
        self._posts = list(post_responses or [])
        self._set_on_get = set_cookies_on_get or {}
        self.get_urls: list[str] = []
        self.post_calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_urls.append(url)
        self.cookies.update(self._set_on_get)
        if not self._gets:
            raise AssertionError("unexpected GET " + url)
        return self._gets.pop(0)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.post_calls.append({"url": url, **kwargs})
        if not self._posts:
            raise AssertionError("unexpected POST " + url)
        return self._posts.pop(0)


# ── 猎聘 ─────────────────────────────────────────────────────────────────────


def _liepin_cards() -> dict[str, Any]:
    return {
        "flag": 1,
        "data": {
            "data": {
                "jobCardList": [
                    {
                        "job": {
                            "jobId": "80438233",
                            "title": "嵌入式测试组长",
                            "salary": "15-30k·15薪",
                            "dq": "深圳-南山区",
                            "link": "https://www.liepin.com/job/1980438233.shtml",
                            "requireWorkYears": "5年以上",
                            "requireEduLevel": "统招本科",
                            "labels": ["嵌入式", "测试"],
                        },
                        "comp": {
                            "compName": "深圳市智能派科技有限公司",
                            "compIndustry": "贸易/进出口",
                        },
                    },
                    {
                        "job": {
                            "jobId": "2",
                            "title": "Python 后端工程师",
                            "salary": "25-40k",
                            "dq": "深圳",
                            "link": "https://www.liepin.com/job/2.shtml",
                        },
                        "comp": {"compName": "示例科技"},
                    },
                ]
            }
        },
    }


def test_liepin_happy_path_parses_cards() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(text="<html>landing</html>")],
        post_responses=[FakeResponse(json_data=_liepin_cards())],
        set_cookies_on_get={"XSRF-TOKEN": "token123"},
    )
    records = LiepinPureHttpConnector(
        "Python", city="深圳", policy=_policy(), session_factory=lambda: session
    ).fetch()

    assert len(records) == 2
    r = records[0]
    assert r.source_kind is SourceKind.CAREER_SITE
    assert r.external_id == "80438233"
    assert r.payload["title"] == "嵌入式测试组长"
    assert r.payload["company"] == "深圳市智能派科技有限公司"
    assert r.payload["salary"] == "15-30k·15薪"
    assert r.payload["location"] == "深圳-南山区"
    assert r.payload["url"] == "https://www.liepin.com/job/1980438233.shtml"
    # composed description carries requirement signal for the ranker
    assert "5年以上" in r.payload["description"]
    assert "统招本科" in r.payload["description"]
    # X-Fscp headers + XSRF were sent
    headers = session.post_calls[0]["headers"]
    assert headers["X-XSRF-TOKEN"] == "token123"
    assert headers["X-Fscp-Version"] == "1.1"
    # city code mapped to dq in the POST body
    body = session.post_calls[0]["json"]["data"]["mainSearchPcConditionForm"]
    assert body["dq"] == "050090"
    assert body["key"] == "Python"


def test_liepin_without_xsrf_cookie_is_blocked() -> None:
    session = FakeSession(get_responses=[FakeResponse(text="landing")])
    with pytest.raises(PureHttpBlockedError):
        LiepinPureHttpConnector(
            "Python", policy=_policy(), session_factory=lambda: session
        ).fetch()


def test_liepin_flag_not_one_is_blocked() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(text="landing")],
        post_responses=[FakeResponse(json_data={"flag": 0, "code": "-1400"})],
        set_cookies_on_get={"XSRF-TOKEN": "t"},
    )
    with pytest.raises(PureHttpBlockedError):
        LiepinPureHttpConnector(
            "Python", policy=_policy(), session_factory=lambda: session
        ).fetch()
