from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jobfindsme.contracts import (
    EmploymentType,
    JobPosting,
    RecruitmentTrack,
    SearchPlan,
)


def make_plan(**overrides: object) -> SearchPlan:
    data: dict[str, object] = {
        "plan_id": "plan-1",
        "workspace_id": "workspace-1",
        "name": "杭州 AI",
        "target_roles": ("AI应用工程师",),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    data.update(overrides)
    return SearchPlan(**data)


def test_search_plan_requires_a_role() -> None:
    with pytest.raises(ValidationError):
        make_plan(target_roles=())


def test_search_plan_rejects_reversed_ranges() -> None:
    with pytest.raises(ValidationError):
        make_plan(salary_min_k=30, salary_max_k=20)
    with pytest.raises(ValidationError):
        make_plan(experience_min_years=5, experience_max_years=3)


def test_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        make_plan(unknown=True)


def test_job_posting_requires_a_valid_salary_range() -> None:
    with pytest.raises(ValidationError):
        JobPosting(
            job_id="job-1",
            external_id="1",
            title="AI工程师",
            company="示例",
            salary_min_k=40,
            salary_max_k=20,
            apply_url="https://example.com/jobs/1",
            fingerprint="f" * 64,
            content_hash="c" * 64,
            source={
                "source_kind": "career_site",
                "source_name": "官网",
                "source_url": "https://example.com",
                "fetched_at": datetime.now(UTC),
            },
        )


def test_job_classification_contracts_reject_unknown_values() -> None:
    with pytest.raises(ValidationError):
        JobPosting(
            job_id="job-1",
            external_id="1",
            title="AI工程师",
            company="示例",
            recruitment_track="experienced-hire",
            employment_type=EmploymentType.FULL_TIME,
            apply_url="https://example.com/jobs/1",
            fingerprint="f" * 64,
            content_hash="c" * 64,
            source={
                "source_kind": "career_site",
                "source_name": "官网",
                "source_url": "https://example.com",
                "fetched_at": datetime.now(UTC),
            },
        )

    assert RecruitmentTrack.CAMPUS.value == "campus"
