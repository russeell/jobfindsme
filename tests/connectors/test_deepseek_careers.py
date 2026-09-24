import json

import pytest

from jobfindsme.connectors.base import ConnectorPolicy
from jobfindsme.connectors.company_careers import CompanyCareerError
from jobfindsme.connectors.deepseek_careers import (
    DeepSeekCareersConnector,
    parse_snapshot,
)
from jobfindsme.research.job_input import canonical_job_url, validate_job_url


def test_snapshot_literal_only_and_complete():
    snapshot = {"jobs": [], "total": 0, "crawledAt": "2026-09-17T00:00:00Z"}
    assert parse_snapshot("JSON.parse(" + repr(json.dumps(snapshot)) + ")") == snapshot
    with pytest.raises(CompanyCareerError):
        parse_snapshot("JSON.parse(fetch('https://example.invalid'))")
    snapshot["total"] = 1
    with pytest.raises(CompanyCareerError):
        parse_snapshot("JSON.parse(" + repr(json.dumps(snapshot)) + ")")


def test_shared_snapshot_cache_and_failure_backoff():
    class Sample(DeepSeekCareersConnector):
        _cache = None
        _retry_after = 0
        reads = 0

        def _read(self, url, limit):
            type(self).reads += 1
            if url == self.home:
                return '<script src="/static/main.123.js"></script>'
            return (
                'JSON.parse(\'{"jobs":[],"total":0,'
                '"crawledAt":"2026-09-17T00:00:00Z"}\')'
            )

    policy = ConnectorPolicy(public_access=True, robots_allowed=True)
    assert Sample("Python", policy=policy).fetch_page() == ([], None)
    assert Sample("Agent", policy=policy).fetch_page() == ([], None)
    assert Sample.reads == 2

    class Failed(Sample):
        _cache = None
        _retry_after = 0

        def _read(self, url, limit):
            raise CompanyCareerError("network unavailable")

    with pytest.raises(CompanyCareerError, match="network unavailable"):
        Failed("a", policy=policy).fetch_page()
    with pytest.raises(CompanyCareerError, match="paused"):
        Failed("b", policy=policy).fetch_page()


def test_ats_tenant_boundary_and_job_identity():
    root = "https://app.mokahr.com/social-recruitment/high-flyer/140576"
    a, b = root + "#/job/a", root + "#/job/b"
    assert validate_job_url(a) == a
    assert canonical_job_url(a) != canonical_job_url(b)
    assert canonical_job_url(a + "?utm_source=x") == a
    for url in [
        root.replace("140576", "999"),
        root.replace("high-flyer", "other"),
        root.replace("https:", "http:"),
    ]:
        with pytest.raises(ValueError):
            validate_job_url(url)
