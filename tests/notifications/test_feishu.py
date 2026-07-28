from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    JobMatch,
    MatchEvidence,
    SourceKind,
)
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.monitoring import MonitorSummary
from jobfindsme.notifications import FeishuNotifier, feishu_signature


class FakeTransport:
    def __init__(self, response=None) -> None:
        self.response = response or {"code": 0}
        self.calls = []

    def post(self, url, payload):
        self.calls.append((url, payload))
        return self.response


def match(index: int) -> JobMatch:
    job = normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="官网",
            source_url="https://example.com",
            external_id=str(index),
            payload={
                "title": f"AI工程师{index}",
                "company": "示例",
                "location": "杭州",
                "url": f"https://example.com/jobs/{index}",
            },
        ),
        fetched_at=datetime(2026, 7, 28, tzinfo=UTC),
    )
    return JobMatch(
        job=job,
        score=0.8,
        evidence=MatchEvidence(hard_filter_passed=True),
    )


def summary(count: int) -> MonitorSummary:
    matches = tuple(match(index) for index in range(count))
    return MonitorSummary(
        workspace_id="workspace",
        plan_id="plan",
        scheduled_for=datetime(2026, 7, 28, tzinfo=UTC),
        matched=matches,
        new_matches=matches,
    )


def test_feishu_signature_matches_official_algorithm_vector() -> None:
    assert feishu_signature(1599360473, "secret") == (
        "q4jswNiMy51J5JuQV566yJat0/lQ/c+22kINzUgKsGU="
    )


def test_notification_is_signed_and_bounded() -> None:
    transport = FakeTransport()
    notifier = FeishuNotifier(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        secret="secret",
        transport=transport,
        clock=lambda: 1599360473,
        max_jobs=2,
        max_chars=500,
    )

    notifier.send(summary(4))

    _, payload = transport.calls[0]
    assert payload["timestamp"] == "1599360473"
    assert payload["sign"] == feishu_signature(1599360473, "secret")
    assert payload["content"]["text"].count("https://example.com/jobs/") == 2
    assert "另有 2 个岗位未展开" in payload["content"]["text"]
    assert len(payload["content"]["text"]) <= 500


def test_notification_can_be_revoked_by_removing_environment(monkeypatch) -> None:
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("FEISHU_SECRET", raising=False)

    assert FeishuNotifier.from_env() is None


def test_partial_or_untrusted_webhook_configuration_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://evil.example/hook")
    monkeypatch.setenv("FEISHU_SECRET", "secret")
    with pytest.raises(ValueError):
        FeishuNotifier.from_env()

    monkeypatch.setenv(
        "FEISHU_WEBHOOK_URL",
        "https://open.feishu.cn/open-apis/bot/v2/hook/test",
    )
    monkeypatch.delenv("FEISHU_SECRET")
    with pytest.raises(ValueError):
        FeishuNotifier.from_env()
