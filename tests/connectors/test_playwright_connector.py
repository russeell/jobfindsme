from __future__ import annotations

from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.playwright import (
    SITE_REGISTRY,
    PlaywrightBrowser,
    PlaywrightSpaConnector,
    SpaSiteConfig,
    _extract_job_list,
)
from jobfindsme.importing.normalizer import normalize_job


def public_policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


class FixtureBrowser:
    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        self.jobs = jobs
        self.calls: list[tuple[SpaSiteConfig, str]] = []

    def collect(
        self,
        config: SpaSiteConfig,
        url: str,
    ) -> list[dict[str, Any]]:
        self.calls.append((config, url))
        return self.jobs


@pytest.mark.parametrize(
    ("site_key", "payload", "expected_title", "expected_location"),
    [
        (
            "bytedance",
            {
                "id": "byte-1",
                "title": "大模型应用工程师",
                "city_info": {"name": "上海"},
                "description": "Python Agent RAG",
            },
            "大模型应用工程师",
            ("上海",),
        ),
        (
            "meituan",
            {
                "jobUnionId": "meituan-1",
                "name": "AI 应用工程师",
                "cityList": [{"name": "北京"}, {"name": "上海"}],
                "desc": "LLM 应用开发",
            },
            "AI 应用工程师",
            ("北京,上海",),
        ),
        (
            "didi",
            {
                "jdId": "didi-1",
                "jobName": "Agent 工程师",
                "workArea": "北京",
                "jobDuty": "负责 Agent 平台",
            },
            "Agent 工程师",
            ("北京",),
        ),
        (
            "bilibili",
            {
                "id": "bili-1",
                "positionName": "RAG 工程师",
                "cityName": "上海",
                "description": "检索增强生成",
            },
            "RAG 工程师",
            ("上海",),
        ),
    ],
)
def test_spa_site_payloads_follow_one_connector_contract(
    site_key: str,
    payload: dict[str, Any],
    expected_title: str,
    expected_location: tuple[str, ...],
) -> None:
    browser = FixtureBrowser([payload])
    connector = PlaywrightSpaConnector(
        site_key,
        "AI 应用",
        policy=public_policy(),
        browser=browser,
    )

    records = connector.fetch()
    job = normalize_job(records[0])

    assert len(records) == 1
    assert job.title == expected_title
    assert job.locations == expected_location
    assert job.company == SITE_REGISTRY[site_key].company_name
    assert "AI+%E5%BA%94%E7%94%A8" in browser.calls[0][1]


def test_duplicate_api_responses_do_not_duplicate_jobs() -> None:
    payload = {
        "id": "same",
        "title": "AI 工程师",
        "city_info": {"name": "上海"},
    }
    connector = PlaywrightSpaConnector(
        "bytedance",
        "AI",
        policy=public_policy(),
        browser=FixtureBrowser([payload, payload]),
    )

    assert len(connector.fetch()) == 1


def test_spa_sources_expose_recruitment_track() -> None:
    bytedance = PlaywrightSpaConnector(
        "bytedance",
        "AI",
        policy=public_policy(),
        browser=FixtureBrowser(
            [{"id": "1", "title": "AI工程师", "city_info": {"name": "上海"}}]
        ),
    ).fetch()[0]
    meituan = PlaywrightSpaConnector(
        "meituan",
        "AI",
        policy=public_policy(),
        browser=FixtureBrowser(
            [{"jobUnionId": "2", "name": "AI实习生", "cityList": ["北京"]}]
        ),
    ).fetch()[0]

    assert bytedance.payload["recruitment_track"] == "social"
    assert meituan.payload["recruitment_track"] == "campus"
    assert bytedance.payload["apply_url"].endswith("/position/1/detail")
    assert (
        meituan.payload["apply_url"]
        == "https://zhaopin.meituan.com/web/position/detail"
        "?jobUnionId=2&highlightType=campus"
    )


def test_nested_response_job_list_is_extracted() -> None:
    body = {"data": {"result": {"job_post_list": [{"id": "1"}]}}}

    assert _extract_job_list(body, "job_post_list") == [{"id": "1"}]


def test_browser_failure_is_not_converted_into_an_empty_success() -> None:
    class FailingBrowser:
        def collect(
            self,
            _config: SpaSiteConfig,
            _url: str,
        ) -> list[dict[str, Any]]:
            raise TimeoutError("career page timed out")

    connector = PlaywrightSpaConnector(
        "bytedance",
        "AI",
        policy=public_policy(),
        browser=FailingBrowser(),
    )

    with pytest.raises(TimeoutError, match="timed out"):
        connector.fetch()


def test_unknown_site_and_disallowed_policy_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown SPA site"):
        PlaywrightSpaConnector(
            "missing",
            "AI",
            policy=public_policy(),
        )
    with pytest.raises(PermissionError):
        PlaywrightSpaConnector(
            "bytedance",
            "AI",
            policy=ConnectorPolicy(public_access=True, robots_allowed=False),
        )


def test_playwright_browser_never_falls_back_to_system_chrome() -> None:
    import inspect

    source = inspect.getsource(PlaywrightBrowser.collect)

    assert 'channel="chrome"' not in source
    assert "system Google Chrome" in source
