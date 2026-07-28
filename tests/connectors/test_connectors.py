from __future__ import annotations

from pathlib import Path
from urllib.request import Request

import pytest

from jobfindsme.connectors import (
    AshbyConnector,
    ConnectorPolicy,
    GreenhouseConnector,
    JsonLdCareerSiteConnector,
)
from jobfindsme.connectors.http import (
    SafeRedirectHandler,
    UnsafeSourceError,
    validate_public_http_url,
)
from jobfindsme.contracts import SourceKind
from jobfindsme.importing.normalizer import normalize_job

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


def test_ashby_reads_only_listed_public_jobs() -> None:
    transport = FixtureTransport(FIXTURES / "ashby_jobs.json")
    connector = AshbyConnector(
        "example",
        transport=transport,
        policy=public_policy(),
        source_name="示例公司",
    )

    records = connector.fetch()

    assert len(records) == 1
    assert records[0].external_id == "ai-app-engineer"
    assert records[0].payload["locations"] == [
        "Shanghai, China",
        "Beijing, China",
    ]
    assert records[0].payload["raw_salary_text"] == "30-45K·13薪"
    assert records[0].payload["currency"] == "CNY"
    assert records[0].payload["salary_period"] == "month"
    assert records[0].payload["salary_min_amount"] == 30000
    assert transport.requested_urls == [
        "https://api.ashbyhq.com/posting-api/job-board/example?includeCompensation=true"
    ]
    normalized = normalize_job(records[0])
    assert normalized.title == "AI 应用工程师"
    assert normalized.locations == ("Shanghai, China", "Beijing, China")
    assert normalized.salary is not None
    assert normalized.salary.currency == "CNY"
    assert normalized.salary.normalized_annual_min == 390_000


def test_ashby_annual_salary_is_not_treated_as_monthly() -> None:
    class AnnualSalaryTransport:
        def get(self, _url: str) -> bytes:
            return (
                b'{"jobs":[{"title":"ML Engineer","location":"Shanghai",'
                b'"isListed":true,"jobUrl":"https://jobs.ashbyhq.com/example/ml",'
                b'"compensation":{"scrapeableCompensationSalarySummary":"$81K - $87K",'
                b'"summaryComponents":[{"compensationType":"Salary",'
                b'"interval":"1 YEAR","currencyCode":"USD",'
                b'"minValue":81000,"maxValue":87000}]}}]}'
            )

    records = AshbyConnector(
        "example",
        transport=AnnualSalaryTransport(),
        policy=public_policy(),
    ).fetch()

    salary = normalize_job(records[0]).salary
    assert salary is not None
    assert salary.period == "year"
    assert salary.normalized_annual_min == 81_000
    assert salary.normalized_annual_max == 87_000


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


def test_redirect_target_is_validated_before_following() -> None:
    handler = SafeRedirectHandler(max_redirects=3, require_https=True)
    request = Request("https://public.example/jobs")

    with pytest.raises(UnsafeSourceError):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://127.0.0.1/private",
        )
