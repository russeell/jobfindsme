"""Tests for the pure-HTTP connectors (猎聘 / 51job / 智联).

These cover the anti-bot boundaries observed live (2026-07-31):
- 猎聘: XSRF cookie + X-Fscp headers → flag=1 JSON; flag!=1 means blocked.
- 51job: Aliyun WAF v1 (arg1) is solved locally; WAF2 JS challenge is not
  solvable and must raise PureHttpBlockedError so discovery falls back.
- 智联: honeypot signature (results=[] + numFound=999999) must raise
  PureHttpBlockedError; a genuine empty result (numFound=0) returns [].

Sessions are fakes — no network, no curl_cffi needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.pure_http import (
    LiepinPureHttpConnector,
    PureHttpBlockedError,
    WuyouPureHttpConnector,
    ZhilianPureHttpConnector,
    acw_sc_v2,
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


# ── acw_sc__v2 solver ────────────────────────────────────────────────────────


def test_acw_sc_v2_shape_and_determinism() -> None:
    arg1 = "0A1B2C3D4E5F60718293A4B5C6D7E8F901234567"
    first = acw_sc_v2(arg1)
    assert len(first) == 40
    assert all(c in "0123456789abcdef" for c in first)
    assert first == acw_sc_v2(arg1)  # deterministic
    assert first != arg1.lower()  # actually transforms


def test_acw_sc_v2_rejects_bad_length() -> None:
    with pytest.raises(ValueError):
        acw_sc_v2("ABCD")


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


# ── 前程无忧 ─────────────────────────────────────────────────────────────────

_WUYOU_ITEMS = {
    "resultbody": {
        "job": {
            "items": [
                {
                    "jobId": "123",
                    "jobName": "大模型应用工程师",
                    "fullCompanyName": "示例科技",
                    "jobDescribe": "RAG/Agent",
                    "jobAreaString": "上海·浦东",
                    "provideSalaryString": "25-40K",
                    "jobHref": "https://we.51job.com/j/123",
                }
            ]
        }
    }
}


def test_wuyou_direct_json_response() -> None:
    session = FakeSession(
        get_responses=[
            FakeResponse(
                json_data=_WUYOU_ITEMS,
                headers={"Content-Type": "application/json"},
            )
        ]
    )
    records = WuyouPureHttpConnector(
        "AI", city="上海", policy=_policy(), session_factory=lambda: session
    ).fetch()
    assert len(records) == 1
    assert records[0].payload["title"] == "大模型应用工程师"
    assert records[0].external_id == "123"


def test_wuyou_solves_waf_v1_then_gets_json() -> None:
    arg1 = "0A1B2C3D4E5F60718293A4B5C6D7E8F901234567"
    challenge = FakeResponse(
        text=f"<script>var arg1='{arg1}';</script>",
        headers={"Content-Type": "text/html"},
    )
    json_resp = FakeResponse(
        json_data=_WUYOU_ITEMS, headers={"Content-Type": "application/json"}
    )
    session = FakeSession(get_responses=[challenge, json_resp])

    records = WuyouPureHttpConnector(
        "AI", city="上海", policy=_policy(), session_factory=lambda: session
    ).fetch()

    assert len(records) == 1
    assert session.cookies.get("acw_sc__v2") == acw_sc_v2(arg1)
    assert len(session.get_urls) == 2  # challenge + retry


def test_wuyou_waf2_challenge_is_blocked_not_silent() -> None:
    waf2 = FakeResponse(
        text='<textarea id="renderData">{"_waf_abc":"..."}</textarea>'
        '<meta name="aliyun_waf_aa" content="...">',
        headers={"Content-Type": "text/html"},
    )
    session = FakeSession(get_responses=[waf2, waf2, waf2])
    with pytest.raises(PureHttpBlockedError):
        WuyouPureHttpConnector(
            "AI", policy=_policy(), session_factory=lambda: session
        ).fetch()


# ── 智联招聘 ─────────────────────────────────────────────────────────────────


def test_zhilian_honeypot_is_blocked_not_empty() -> None:
    honeypot = {
        "code": 200,
        "data": {"results": [], "numTotal": 0, "numFound": 999999},
    }
    session = FakeSession(
        get_responses=[
            FakeResponse(text="landing"),
            FakeResponse(json_data=honeypot),
        ]
    )
    with pytest.raises(PureHttpBlockedError):
        ZhilianPureHttpConnector(
            "Python", city="深圳", policy=_policy(), session_factory=lambda: session
        ).fetch()


def test_zhilian_genuine_empty_result_is_trusted() -> None:
    empty = {"code": 200, "data": {"results": [], "numTotal": 0, "numFound": 0}}
    session = FakeSession(
        get_responses=[FakeResponse(text="landing"), FakeResponse(json_data=empty)]
    )
    records = ZhilianPureHttpConnector(
        "极稀有关键词", policy=_policy(), session_factory=lambda: session
    ).fetch()
    assert records == []


def test_zhilian_parses_results() -> None:
    payload = {
        "code": 200,
        "data": {
            "results": [
                {
                    "number": "CC001",
                    "jobName": "Python 后端",
                    "companyName": "示例智能",
                    "jobSummary": "FastAPI",
                    "workCity": {"name": "深圳"},
                    "salary60": "20-35K",
                    "positionURL": "https://jobs.zhaopin.com/CC001",
                }
            ],
            "numFound": 1,
        },
    }
    session = FakeSession(
        get_responses=[FakeResponse(text="landing"), FakeResponse(json_data=payload)]
    )
    records = ZhilianPureHttpConnector(
        "Python", city="深圳", policy=_policy(), session_factory=lambda: session
    ).fetch()
    assert len(records) == 1
    assert records[0].payload["title"] == "Python 后端"
    assert records[0].payload["location"] == "深圳"
    # full param set incl. lastUrlQuery was sent to the real endpoint
    assert session.get_urls[-1].startswith("https://fe-api.zhaopin.com/c/i/sou")
