from __future__ import annotations

import json
from typing import Any

from jobfindsme.connectors.base import ConnectorPolicy, RawJobRecord
from jobfindsme.connectors.http import HttpTransport, validate_public_http_url
from jobfindsme.contracts import SourceKind


def _salary_payload(item: dict[str, Any]) -> dict[str, Any]:
    compensation = item.get("compensation")
    if not isinstance(compensation, dict):
        return {}

    raw_text = compensation.get("scrapeableCompensationSalarySummary")
    components = compensation.get("summaryComponents")
    salary_component = next(
        (
            component
            for component in components or []
            if isinstance(component, dict)
            and component.get("compensationType") == "Salary"
        ),
        None,
    )
    result: dict[str, Any] = {}
    if raw_text:
        result["raw_salary_text"] = raw_text
    if salary_component and salary_component.get("currencyCode"):
        result["currency"] = salary_component["currencyCode"]
    if salary_component:
        interval = str(salary_component.get("interval") or "").upper()
        period = {
            "1 YEAR": "year",
            "1 MONTH": "month",
            "1 DAY": "day",
            "1 HOUR": "hour",
        }.get(interval)
        if period:
            result["salary_period"] = period
        if salary_component.get("minValue") is not None:
            result["salary_min_amount"] = int(salary_component["minValue"])
        if salary_component.get("maxValue") is not None:
            result["salary_max_amount"] = int(salary_component["maxValue"])
    return result


def _normalize_payload(item: dict[str, Any]) -> dict[str, Any]:
    locations = [item.get("location")]
    locations.extend(
        location.get("location")
        for location in item.get("secondaryLocations") or []
        if isinstance(location, dict)
    )
    return {
        "title": item.get("title"),
        "description": item.get("descriptionPlain")
        or item.get("descriptionHtml")
        or "",
        "locations": [location for location in locations if location],
        "published_at": item.get("publishedAt"),
        "url": item.get("jobUrl"),
        "apply_url": item.get("applyUrl") or item.get("jobUrl"),
        "department": item.get("department"),
        "team": item.get("team"),
        "employment_type": item.get("employmentType"),
        "workplace_type": item.get("workplaceType"),
        **_salary_payload(item),
    }


class AshbyConnector:
    """Read published jobs from Ashby's documented public job-board API."""

    def __init__(
        self,
        board_name: str,
        *,
        transport: HttpTransport,
        policy: ConnectorPolicy,
        source_name: str | None = None,
    ) -> None:
        if not policy.can_fetch:
            raise PermissionError("source policy does not allow fetching")
        if not board_name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("invalid Ashby board name")
        self.board_name = board_name
        self.transport = transport
        self.source_name = source_name or f"ashby:{board_name}"

    def fetch(self) -> list[RawJobRecord]:
        url = (
            "https://api.ashbyhq.com/posting-api/job-board/"
            f"{self.board_name}?includeCompensation=true"
        )
        validate_public_http_url(url, require_https=True)
        document = json.loads(self.transport.get(url))
        records: list[RawJobRecord] = []
        for index, item in enumerate(document.get("jobs", [])):
            if not isinstance(item, dict) or item.get("isListed") is False:
                continue
            job_url = str(item.get("jobUrl") or item.get("applyUrl") or "")
            external_id = job_url.rsplit("/", 1)[-1] or f"{self.board_name}-{index}"
            records.append(
                RawJobRecord(
                    source_kind=SourceKind.ATS,
                    source_name=self.source_name,
                    source_url=url,
                    external_id=external_id,
                    payload=_normalize_payload(item),
                )
            )
        return records
