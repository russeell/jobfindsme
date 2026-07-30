"""Tests for the passive Network-interception connectors (51job / 智联).

These cover the parts that broke in the field:
- 51job city code mapping uses ``jobArea`` (not ``location``) so the SPA
  actually applies the filter instead of falling back to IP geolocation.
- 智联 intercept pattern is ``/c/i/sou`` (the SPA's real endpoint) — the
  earlier ``portal/job/search`` pattern 404s and never matches.
- Transport failure raises ``InterceptionFailedError`` so discovery can
  fall back to DOM instead of silently returning 0 jobs.
"""

from __future__ import annotations

from typing import Any

import pytest

from jobfindsme.connectors import http_platforms
from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.http_platforms import (
    InterceptionFailedError,
    WuyouHttpConnector,
    ZhilianHttpConnector,
)
from jobfindsme.contracts import SourceKind


def _policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


def _stub_intercept(payload: Any):
    """Replace _intercept_api_response with a stub returning *payload*.

    Captures the search_url it was called with so URL-construction tests
    can assert on it.
    """

    calls: list[str] = []

    def _fake(search_url, _patterns, **_kwargs):  # noqa: ANN001
        calls.append(search_url)
        return payload

    return _fake, calls


# ── 51job ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("city", "expected_code"),
    [
        ("上海", "020000"),
        ("北京", "010000"),
        ("深圳", "040000"),
        ("广州", "030200"),
        ("杭州", "080200"),
    ],
)
def test_wuyou_city_mapping(city: str, expected_code: str) -> None:
    assert http_platforms._WUYOU_CITY[city] == expected_code


def test_wuyou_search_url_uses_jobarea_not_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake, calls = _stub_intercept({"resultbody": {"job": {"items": []}}})
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    WuyouHttpConnector("AI", city="上海", policy=_policy()).fetch()

    assert calls, "intercept was never called"
    url = calls[0]
    assert "jobArea=020000" in url
    assert "location=" not in url


def test_wuyou_unknown_city_falls_back_to_nationwide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake, calls = _stub_intercept({"resultbody": {"job": {"items": []}}})
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    WuyouHttpConnector("AI", city="未知城市", policy=_policy()).fetch()
    assert "jobArea=000000" in calls[0]


def test_wuyou_raises_on_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        http_platforms, "_intercept_api_response", lambda *_a, **_k: None
    )

    with pytest.raises(InterceptionFailedError):
        WuyouHttpConnector("AI", policy=_policy()).fetch()


def test_wuyou_parses_structured_items(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "resultbody": {
            "job": {
                "items": [
                    {
                        "jobId": "123",
                        "jobName": "大模型应用工程师",
                        "fullCompanyName": "示例科技",
                        "jobDescribe": "RAG/Agent 方向",
                        "jobAreaString": "上海·浦东",
                        "provideSalaryString": "25-40K",
                        "jobHref": "https://we.51job.com/j/123",
                    }
                ]
            }
        }
    }
    fake, _ = _stub_intercept(payload)
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    records = WuyouHttpConnector("AI", city="上海", policy=_policy()).fetch()
    assert len(records) == 1
    r = records[0]
    assert r.source_kind is SourceKind.CAREER_SITE
    assert r.payload["title"] == "大模型应用工程师"
    assert r.payload["company"] == "示例科技"
    assert r.payload["salary"] == "25-40K"
    assert r.payload["url"] == "https://we.51job.com/j/123"
    assert r.external_id == "123"


def test_wuyou_empty_but_successful_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Successful API call with no jobs must NOT raise — distinct from transport failure.
    fake, _ = _stub_intercept({"resultbody": {"job": {"items": []}}})
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    assert WuyouHttpConnector("稀有关键词", policy=_policy()).fetch() == []


# ── 智联招聘 ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("city", "expected_id"),
    [
        ("上海", "538"),
        ("北京", "530"),
        ("深圳", "765"),
        ("广州", "763"),
        ("杭州", "653"),
    ],
)
def test_zhilian_city_mapping(city: str, expected_id: str) -> None:
    assert http_platforms._ZHILIAN_CITY[city] == expected_id


def test_zhilian_search_url_uses_jl_cityid(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = _stub_intercept({"data": {"results": []}})
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    ZhilianHttpConnector("python", city="上海", policy=_policy()).fetch()

    assert calls
    url = calls[0]
    assert "jl=538" in url
    assert "kw=python" in url


def test_zhilian_intercept_pattern_is_real_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The stub ignores patterns, but the connector must pass the *real*
    # fe-api /c/i/sou pattern (the old portal/job/search one 404s).
    captured: list[tuple[str, ...]] = []

    def fake(search_url, patterns, **_kwargs):
        captured.append(patterns)
        return {"data": {"results": []}}

    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)
    ZhilianHttpConnector("python", city="上海", policy=_policy()).fetch()
    assert captured
    assert any("/c/i/sou" in p for p in captured[0])


def test_zhilian_raises_on_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        http_platforms, "_intercept_api_response", lambda *_a, **_k: None
    )

    with pytest.raises(InterceptionFailedError):
        ZhilianHttpConnector("AI", policy=_policy()).fetch()


def test_zhilian_parses_sou_api_items(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "data": {
            "results": [
                {
                    "number": "CC001",
                    "jobName": "Python 后端",
                    "companyName": "示例智能",
                    "jobSummary": "FastAPI / 微服务",
                    "workCity": "上海",
                    "salary60": "20-35K",
                    "positionURL": "https://jobs.zhaopin.com/CC001",
                }
            ]
        }
    }
    fake, _ = _stub_intercept(payload)
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    records = ZhilianHttpConnector("python", city="上海", policy=_policy()).fetch()
    assert len(records) == 1
    r = records[0]
    assert r.payload["title"] == "Python 后端"
    assert r.payload["company"] == "示例智能"
    assert r.payload["salary"] == "20-35K"
    assert r.payload["location"] == "上海"
    assert r.external_id == "CC001"


def test_zhilian_workcity_dict_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "data": {
            "results": [
                {
                    "number": "X1",
                    "jobName": "全栈",
                    "companyName": "示例信息",
                    "workCity": {"name": "杭州"},
                    "salary60": "30K",
                }
            ]
        }
    }
    fake, _ = _stub_intercept(payload)
    monkeypatch.setattr(http_platforms, "_intercept_api_response", fake)

    records = ZhilianHttpConnector("全栈", city="杭州", policy=_policy()).fetch()
    assert records[0].payload["location"] == "杭州"
