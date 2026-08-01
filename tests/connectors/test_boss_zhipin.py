from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.boss_zhipin import (
    BOSS_ORIGIN,
    BOSS_PROFILE_DIR,
    BossAuthenticationRequired,
    BossConnectorError,
    BossZhipinConnector,
    _CDPSession,
    _chrome_command,
    setup_chrome,
)
from jobfindsme.importing.normalizer import normalize_job


def public_policy() -> ConnectorPolicy:
    return ConnectorPolicy(public_access=True, robots_allowed=True)


class FakeCdp:
    def __init__(self, api_payload: dict[str, Any] | None = None) -> None:
        self.api_payload = api_payload or {"jobs": []}
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.closed = False
        self.target_closed = False
        self.evaluated_js: list[str] = []

    def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        sid: str | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        self.calls.append((method, params, sid))
        if method == "Target.createTarget":
            return {"result": {"targetId": "target-1"}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": "session-1"}}
        if method == "Target.closeTarget":
            self.target_closed = True
        return {"result": {}}

    def eval_js(self, js: str, _sid: str) -> Any:
        if js == "document.readyState":
            return "complete"
        self.evaluated_js.append(js)
        assert f"{BOSS_ORIGIN}/wapi/" in js
        assert 'credentials: "include"' in js
        assert "await fetch(" in js
        assert "XMLHttpRequest" not in js
        return json.dumps(self.api_payload)

    def close(self) -> None:
        self.closed = True


def connector(fake: FakeCdp) -> BossZhipinConnector:
    return BossZhipinConnector(
        "AI 应用工程师",
        city="101020100",
        policy=public_policy(),
        session_factory=lambda _port: fake,
    )


def test_cdp_runtime_evaluation_awaits_async_fetch_promise() -> None:
    session = object.__new__(_CDPSession)
    captured: dict[str, Any] = {}

    def send(method, params=None, sid=None):
        captured.update(method=method, params=params, sid=sid)
        return {"result": {"result": {"value": "ok"}}}

    session.send = send

    assert session.eval_js("Promise.resolve('ok')", "session-1") == "ok"
    assert captured["method"] == "Runtime.evaluate"
    assert captured["params"]["awaitPromise"] is True
    assert captured["params"]["returnByValue"] is True


def test_boss_navigates_to_origin_before_same_origin_api_and_closes_resources() -> None:
    fake = FakeCdp()

    assert connector(fake).fetch() == []

    methods = [item[0] for item in fake.calls]
    navigate_index = methods.index("Page.navigate")
    assert fake.calls[navigate_index][1]["url"] == f"{BOSS_ORIGIN}/web/geek/job"
    assert methods.index("Runtime.enable") < navigate_index
    assert fake.target_closed is True
    assert fake.closed is True


def test_boss_payload_maps_salary_location_skills_and_job_link() -> None:
    fake = FakeCdp(
        {
            "jobs": [
                {
                    "job_id": "encrypted-1",
                    "title": "AI应用工程师",
                    "salary": "20-30K·13薪",
                    "location": "上海 · 浦东新区",
                    "company": "示例科技",
                    "experience": "1-3年",
                    "degree": "本科",
                    "skills": "Python, RAG, Agent",
                    "job_labels": "双休",
                    "welfare": "五险一金",
                    "job_link": "https://www.zhipin.com/job_detail/encrypted-1.html",
                }
            ]
        }
    )

    records = connector(fake).fetch()
    job = normalize_job(records[0])

    assert records[0].external_id == "encrypted-1"
    assert job.title == "AI应用工程师"
    assert job.company == "示例科技"
    assert job.salary is not None
    assert job.salary.normalized_annual_min == 260_000
    assert job.locations == ("上海 · 浦东新区",)
    assert "Python" in job.description
    assert job.apply_url.endswith("encrypted-1.html")
    assert job.recruitment_track == "social"
    assert job.employment_type == "full_time"


def test_boss_classifies_campus_internship_from_visible_labels() -> None:
    fake = FakeCdp(
        {
            "jobs": [
                {
                    "job_id": "intern-1",
                    "title": "AI应用工程师实习生",
                    "job_labels": "2027届校园招聘",
                    "company": "示例科技",
                    "location": "杭州",
                    "salary": "300-400元/天",
                    "job_link": "https://www.zhipin.com/job_detail/intern-1.html",
                }
            ]
        }
    )

    job = normalize_job(connector(fake).fetch()[0])

    assert job.recruitment_track == "campus"
    assert job.employment_type == "internship"


def test_boss_translates_supported_chinese_city_to_api_code() -> None:
    fake = FakeCdp()
    BossZhipinConnector(
        "AI应用工程师",
        city="杭州",
        policy=public_policy(),
        session_factory=lambda _port: fake,
    ).fetch()

    assert any("city=101210100" in js for js in fake.evaluated_js)


def test_authentication_failure_is_distinct_and_resources_are_closed() -> None:
    fake = FakeCdp({"error": "authentication_required", "status": 401})

    with pytest.raises(BossAuthenticationRequired, match="Log in"):
        connector(fake).fetch()

    assert fake.target_closed is True
    assert fake.closed is True


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "http_error", "status": 429},
        {"unexpected": []},
    ],
)
def test_protocol_failures_are_not_reported_as_empty_success(payload) -> None:
    fake = FakeCdp(payload)

    with pytest.raises(BossConnectorError):
        connector(fake).fetch()

    assert fake.closed is True


def test_invalid_json_and_missing_cdp_are_clear_failures() -> None:
    with pytest.raises(BossConnectorError, match="invalid JSON"):
        BossZhipinConnector._parse_response("<html>")

    def unavailable(_port: int):
        raise BossConnectorError("CDP unavailable")

    with pytest.raises(BossConnectorError, match="unavailable"):
        BossZhipinConnector(
            "AI",
            policy=public_policy(),
            session_factory=unavailable,
        ).fetch()


def test_disallowed_policy_is_rejected() -> None:
    with pytest.raises(PermissionError):
        BossZhipinConnector(
            "AI",
            policy=ConnectorPolicy(public_access=True, robots_allowed=False),
        )


def test_chrome_command_keeps_the_browser_sandbox_enabled() -> None:
    command = _chrome_command(
        "/Applications/Google Chrome",
        "/tmp/jobfindsme-profile",
        ["https://www.zhipin.com/web/user/"],
    )

    assert "--no-sandbox" not in command
    assert "--disable-gpu-sandbox" not in command
    assert "--disable-gpu" not in command
    assert "--remote-debugging-port=9222" in command


def test_setup_chrome_skips_launch_when_cdp_already_reachable(
    monkeypatch,
) -> None:
    """setup when the bridge is already up must NOT launch a new Chrome."""
    launched = []

    def fake_reachable(*args, **kwargs):
        return True

    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._cdp_reachable", fake_reachable
    )
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: launched.append(a))

    result = setup_chrome()

    assert result["ok"] is True
    assert "已在运行" in result["message"]
    assert launched == []  # no new Chrome process

    # PID file must not be touched by the already-running path
    profile = Path(BOSS_PROFILE_DIR).expanduser()
    pid_file = profile / "chrome.pid"
    before = pid_file.read_text() if pid_file.exists() else None
    assert before is None or pid_file.read_text() == before
