from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    JobLiveness,
    JobPosting,
    SalaryDetails,
    SalaryPeriod,
    SourceEvidence,
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(r"(\d+)\s*(?:[-~到至]\s*(\d+))?\s*年")
_SALARY_RE = re.compile(r"(\d+)\s*[-~到至]\s*(\d+)\s*[kK]")
_MONTHLY_SALARY_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-~到至]\s*(\d+(?:\.\d+)?)\s*[kK]"
    r"(?:\s*[·xX*]\s*(\d{1,2})\s*薪)?"
)
_ANNUAL_WAN_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-~到至]\s*(\d+(?:\.\d+)?)\s*万\s*/?\s*年"
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", str(value)))).strip()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def _company(payload: dict[str, Any], fallback: str) -> str:
    organization = payload.get("hiringOrganization")
    if isinstance(organization, dict):
        return _text(organization.get("name")) or fallback
    return _text(payload.get("company") or payload.get("company_name")) or fallback


def _locations(payload: dict[str, Any]) -> tuple[str, ...]:
    direct = payload.get("locations") or payload.get("location")
    if isinstance(direct, list):
        values = [
            _text(item.get("name") if isinstance(item, dict) else item)
            for item in direct
        ]
    elif isinstance(direct, dict):
        values = [_text(direct.get("name"))]
    elif direct:
        values = [_text(direct)]
    else:
        job_location = payload.get("jobLocation")
        if not isinstance(job_location, list):
            job_location = [job_location] if job_location else []
        values = []
        for item in job_location:
            address = item.get("address", {}) if isinstance(item, dict) else {}
            parts = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            values.append(" ".join(_text(part) for part in parts if part))
    return tuple(dict.fromkeys(value for value in values if value))


def normalize_job(
    raw: RawJobRecord,
    *,
    fetched_at: datetime | None = None,
    stale_after_days: int = 45,
) -> JobPosting:
    payload = dict(raw.payload)
    now = fetched_at or datetime.now(UTC)
    title = _text(payload.get("title") or payload.get("name"))
    company = _company(payload, raw.source_name)
    description = _text(payload.get("description") or payload.get("content"))
    locations = _locations(payload)
    apply_url = _text(
        payload.get("apply_url") or payload.get("absolute_url") or payload.get("url")
    )
    published_at = _parse_datetime(
        payload.get("published_at")
        or payload.get("updated_at")
        or payload.get("datePosted")
    )
    closed = bool(payload.get("closed") or payload.get("is_closed"))
    if closed:
        liveness = JobLiveness.CLOSED
    elif published_at and now - published_at > timedelta(days=stale_after_days):
        liveness = JobLiveness.STALE
    elif published_at:
        liveness = JobLiveness.ACTIVE
    else:
        liveness = JobLiveness.UNKNOWN

    combined = f"{title} {description}"
    salary_match = _SALARY_RE.search(combined)
    salary_details = _parse_salary(payload, combined)
    experience = _YEAR_RE.search(combined)
    salary_min = int(payload["salary_min_k"]) if payload.get("salary_min_k") else None
    salary_max = int(payload["salary_max_k"]) if payload.get("salary_max_k") else None
    if salary_match and salary_min is None and salary_max is None:
        salary_min, salary_max = map(int, salary_match.groups())
    experience_min = (
        int(payload["experience_min_years"])
        if payload.get("experience_min_years") is not None
        else None
    )
    experience_max = (
        int(payload["experience_max_years"])
        if payload.get("experience_max_years") is not None
        else None
    )
    if experience and experience_min is None and experience_max is None:
        experience_min = int(experience.group(1))
        experience_max = int(experience.group(2) or experience.group(1))

    fingerprint_input = "|".join(
        [
            company.casefold(),
            title.casefold(),
            "|".join(locations).casefold(),
        ]
    )
    content_input = "|".join(
        [fingerprint_input, description, str(salary_min), str(salary_max)]
    )
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()
    content_hash = hashlib.sha256(content_input.encode()).hexdigest()
    return JobPosting(
        job_id=f"job_{fingerprint[:24]}",
        external_id=raw.external_id,
        title=title,
        company=company,
        description=description,
        locations=locations,
        salary_min_k=salary_min,
        salary_max_k=salary_max,
        salary=salary_details,
        experience_min_years=experience_min,
        experience_max_years=experience_max,
        apply_url=apply_url or raw.source_url,
        fingerprint=fingerprint,
        content_hash=content_hash,
        source=SourceEvidence(
            source_kind=raw.source_kind,
            source_name=raw.source_name,
            source_url=raw.source_url,
            fetched_at=now,
            published_at=published_at,
            liveness=liveness,
        ),
    )


def _parse_salary(payload: dict[str, Any], text: str) -> SalaryDetails | None:
    raw_value = payload.get("raw_salary_text") or payload.get("salary")
    raw_text = _text(raw_value)
    search_text = raw_text or text
    structured_period = payload.get("salary_period")
    structured_min = payload.get("salary_min_amount")
    structured_max = payload.get("salary_max_amount")

    if structured_period and (structured_min is not None or structured_max is not None):
        period = SalaryPeriod(str(structured_period))
        minimum = int(structured_min) if structured_min is not None else None
        maximum = int(structured_max) if structured_max is not None else None
        monthly_match = _MONTHLY_SALARY_RE.search(raw_text)
        months = (
            int(monthly_match.group(3) or 12)
            if period is SalaryPeriod.MONTH and monthly_match
            else 12
            if period is SalaryPeriod.MONTH
            else None
        )
        annual_factor = (
            months
            if period is SalaryPeriod.MONTH
            else 1
            if period is SalaryPeriod.YEAR
            else None
        )
        return SalaryDetails(
            raw_text=raw_text or f"{minimum or ''}-{maximum or ''}",
            currency=(
                str(payload["currency"]).upper() if payload.get("currency") else None
            ),
            period=period,
            min_amount=minimum,
            max_amount=maximum,
            months_per_year=months,
            normalized_annual_min=(
                minimum * annual_factor
                if minimum is not None and annual_factor is not None
                else None
            ),
            normalized_annual_max=(
                maximum * annual_factor
                if maximum is not None and annual_factor is not None
                else None
            ),
        )

    monthly = _MONTHLY_SALARY_RE.search(search_text)
    if monthly:
        minimum = int(float(monthly.group(1)) * 1000)
        maximum = int(float(monthly.group(2)) * 1000)
        months = int(monthly.group(3) or 12)
        return SalaryDetails(
            raw_text=monthly.group(0),
            currency=str(payload.get("currency") or "CNY").upper(),
            period=SalaryPeriod.MONTH,
            min_amount=minimum,
            max_amount=maximum,
            months_per_year=months,
            normalized_annual_min=minimum * months,
            normalized_annual_max=maximum * months,
        )

    annual = _ANNUAL_WAN_RE.search(search_text)
    if annual:
        minimum = int(float(annual.group(1)) * 10_000)
        maximum = int(float(annual.group(2)) * 10_000)
        return SalaryDetails(
            raw_text=annual.group(0),
            currency=str(payload.get("currency") or "CNY").upper(),
            period=SalaryPeriod.YEAR,
            min_amount=minimum,
            max_amount=maximum,
            normalized_annual_min=minimum,
            normalized_annual_max=maximum,
        )

    if raw_text:
        return SalaryDetails(
            raw_text=raw_text,
            currency=(
                str(payload["currency"]).upper() if payload.get("currency") else None
            ),
        )
    if "面议" in text:
        return SalaryDetails(raw_text="面议")
    return None
