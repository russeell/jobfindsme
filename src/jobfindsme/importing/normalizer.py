from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import (
    EmploymentType,
    JobDetailLevel,
    JobLiveness,
    JobPosting,
    RecruitmentTrack,
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

_CAMPUS_TERMS = ("校招", "校园招聘", "应届", "毕业生", "campus", "new grad", "graduate")
_SOCIAL_TERMS = ("社招", "社会招聘", "experienced", "social recruitment")
_INTERNSHIP_TERMS = ("实习", "internship", "intern")
_FULL_TIME_TERMS = ("正式岗", "正式岗位", "全职", "full-time", "full time", "fulltime")
_PART_TIME_TERMS = ("兼职", "part-time", "part time")
_CONTRACT_TERMS = ("合同工", "劳务合同", "contractor", "contract")


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
    detail_level = JobDetailLevel(
        payload.get("detail_level")
        or (
            JobDetailLevel.STRUCTURED_SOURCE
            if description
            else JobDetailLevel.LIST_CARD
        )
    )
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
    elif fetched_at:
        # Freshly fetched without explicit timestamp → assume active
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
    # Fallback: extract K values from parsed salary_details
    if salary_min is None and salary_details and salary_details.min_amount:
        salary_min = salary_details.min_amount // 1000
    if salary_max is None and salary_details and salary_details.max_amount:
        salary_max = salary_details.max_amount // 1000
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

    recruitment_track = _recruitment_track(payload, title, description, raw.source_url)
    employment_type = _employment_type(payload, title, description)

    fingerprint_input = "|".join(
        [
            company.casefold(),
            title.casefold(),
            "|".join(locations).casefold(),
        ]
    )
    content_input = "|".join(
        [
            fingerprint_input,
            description,
            str(salary_min),
            str(salary_max),
            recruitment_track,
            employment_type,
        ]
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
        recruitment_track=recruitment_track,
        employment_type=employment_type,
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
            detail_level=detail_level,
            description_source_url=_text(payload.get("description_source_url")) or None,
            description_fetched_at=(
                now if detail_level is JobDetailLevel.DETAIL_PAGE else None
            ),
        ),
    )


def _recruitment_track(
    payload: dict[str, Any],
    title: str,
    description: str,
    source_url: str,
) -> RecruitmentTrack:
    explicit = _text(
        payload.get("recruitment_track") or payload.get("recruitment_type")
    ).casefold()
    aliases = {
        "campus": RecruitmentTrack.CAMPUS,
        "校招": RecruitmentTrack.CAMPUS,
        "校园招聘": RecruitmentTrack.CAMPUS,
        "social": RecruitmentTrack.SOCIAL,
        "社招": RecruitmentTrack.SOCIAL,
        "社会招聘": RecruitmentTrack.SOCIAL,
        "experienced": RecruitmentTrack.SOCIAL,
    }
    if explicit in aliases:
        return aliases[explicit]

    content = f"{title} {description}".casefold()
    if any(term in content for term in _CAMPUS_TERMS):
        return RecruitmentTrack.CAMPUS
    if any(term in content for term in _SOCIAL_TERMS):
        return RecruitmentTrack.SOCIAL

    source = source_url.casefold()
    if any(term in source for term in ("campus", "school", "graduate")):
        return RecruitmentTrack.CAMPUS
    if any(term in source for term in ("social", "experienced")):
        return RecruitmentTrack.SOCIAL
    return RecruitmentTrack.UNKNOWN


def _employment_type(
    payload: dict[str, Any],
    title: str,
    description: str,
) -> EmploymentType:
    explicit = _text(
        payload.get("employment_type")
        or payload.get("employmentType")
        or payload.get("job_type")
    ).casefold()
    aliases = {
        "intern": EmploymentType.INTERNSHIP,
        "internship": EmploymentType.INTERNSHIP,
        "实习": EmploymentType.INTERNSHIP,
        "fulltime": EmploymentType.FULL_TIME,
        "full_time": EmploymentType.FULL_TIME,
        "full-time": EmploymentType.FULL_TIME,
        "full time": EmploymentType.FULL_TIME,
        "全职": EmploymentType.FULL_TIME,
        "正式": EmploymentType.FULL_TIME,
        "parttime": EmploymentType.PART_TIME,
        "part_time": EmploymentType.PART_TIME,
        "part-time": EmploymentType.PART_TIME,
        "兼职": EmploymentType.PART_TIME,
        "contract": EmploymentType.CONTRACT,
        "contractor": EmploymentType.CONTRACT,
        "合同": EmploymentType.CONTRACT,
    }
    if explicit in aliases:
        return aliases[explicit]

    title_text = title.casefold()
    if any(term in title_text for term in _INTERNSHIP_TERMS):
        return EmploymentType.INTERNSHIP
    if any(term in title_text for term in _PART_TIME_TERMS):
        return EmploymentType.PART_TIME
    if any(term in title_text for term in _CONTRACT_TERMS):
        return EmploymentType.CONTRACT
    if any(term in title_text for term in _FULL_TIME_TERMS):
        return EmploymentType.FULL_TIME

    description_text = description.casefold()
    if any(term in description_text for term in ("实习岗位", "internship position")):
        return EmploymentType.INTERNSHIP
    if any(term in description_text for term in ("兼职岗位", "part-time position")):
        return EmploymentType.PART_TIME
    if any(term in description_text for term in ("合同岗位", "contract position")):
        return EmploymentType.CONTRACT
    if any(
        term in description_text
        for term in ("正式岗位", "全职岗位", "full-time position")
    ):
        return EmploymentType.FULL_TIME
    return EmploymentType.UNKNOWN


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
