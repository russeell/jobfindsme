from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import JobLiveness, JobPosting, SourceEvidence

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(r"(\d+)\s*(?:[-~到至]\s*(\d+))?\s*年")
_SALARY_RE = re.compile(r"(\d+)\s*[-~到至]\s*(\d+)\s*[kK]")


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
    salary = _SALARY_RE.search(combined)
    experience = _YEAR_RE.search(combined)
    salary_min = int(payload["salary_min_k"]) if payload.get("salary_min_k") else None
    salary_max = int(payload["salary_max_k"]) if payload.get("salary_max_k") else None
    if salary and salary_min is None and salary_max is None:
        salary_min, salary_max = map(int, salary.groups())
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
            apply_url,
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
