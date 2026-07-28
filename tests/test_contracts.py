from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jobfindsme.contracts import SearchPlan


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
