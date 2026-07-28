from __future__ import annotations

from pathlib import Path

import pytest

from jobfindsme.connectors import (
    ConnectorPolicy,
    GreenhouseConnector,
    JsonLdCareerSiteConnector,
)
from jobfindsme.connectors.http import UnsafeSourceError, validate_public_http_url
from jobfindsme.contracts import SourceKind

FIXTURES = Path(__file__).parents[2] / "data" / "fixtures"


class FixtureTransport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.requested_urls: list[str] = []

    def get(self, url: str) -> bytes:
        self.requested_urls.append(url)
        return self.path.read_bytes()


def public_policy() -> ConnectorPolicy:
    return ConnectorPolicy(
        public_access=True,
        robots_allowed=True,
    )


def test_greenhouse_reads_public_job_board_contract() -> None:
    transport = FixtureTransport(FIXTURES / "greenhouse_jobs.json")
    connector = GreenhouseConnector(
        "example-board",
        transport=transport,
        policy=public_policy(),
    )

    records = connector.fetch()

    assert len(records) == 1
    assert records[0].external_id == "1001"
    assert records[0].source_kind == SourceKind.ATS
    assert transport.requested_urls == [
        "https://boards-api.greenhouse.io/v1/boards/example-board/jobs?content=true"
    ]


def test_official_site_reads_schema_org_job_posting() -> None:
    connector = JsonLdCareerSiteConnector(
        "https://careers.example.com/jobs/official-42",
        transport=FixtureTransport(FIXTURES / "official_career_job.html"),
        policy=public_policy(),
        source_name="示例科技官网",
    )

    records = connector.fetch()

    assert len(records) == 1
    assert records[0].external_id == "official-42"
    assert records[0].payload["title"] == "大模型应用工程师"
    assert records[0].source_kind == SourceKind.CAREER_SITE


def test_connector_refuses_unapproved_source_policy() -> None:
    policy = ConnectorPolicy(public_access=True, robots_allowed=False)
    with pytest.raises(PermissionError):
        GreenhouseConnector(
            "example",
            transport=FixtureTransport(FIXTURES / "greenhouse_jobs.json"),
            policy=policy,
        )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/jobs",
        "http://127.0.0.1/jobs",
        "https://user:secret@example.com/jobs",
    ],
)
def test_url_validation_blocks_local_or_credentialed_sources(url: str) -> None:
    with pytest.raises(UnsafeSourceError):
        validate_public_http_url(url)
