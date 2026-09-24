from types import SimpleNamespace

import pytest

from jobfindsme.search.jobs import DesktopJobFilters
from jobfindsme.search.rules import DEFAULT_WEIGHTS, evaluate, work_years
from tests.desktop_api.test_job_snapshots import _job, _services


def test_four_dimensions_use_confirmed_sections_and_actual_requirements():
    job = _job(
        1, description="Python FastAPI，要求本科及以上学历，3年以上工作经验"
    ).model_copy(update={"experience_min_years": 3})
    resume = SimpleNamespace(
        content={
            "skills": ["Python FastAPI"],
            "projects": ["负责开发Python FastAPI订单服务"],
            "education": ["已毕业 本科学士"],
            "experience": ["3年工作经验"],
        }
    )
    result = evaluate(job, resume, DEFAULT_WEIGHTS)
    assert result["score"] == 100
    assert result["components"] == DEFAULT_WEIGHTS
    assert result["coverage"] == 1
    assert all(v["status"] == "known" for v in result["details"].values())


def test_missing_education_experience_and_bare_skills_do_not_earn_credit():
    job = _job(1, description="要求硕士及以上学历，Python FastAPI")
    resume = SimpleNamespace(
        content={
            "skills": ["Python FastAPI"],
            "projects": ["Python FastAPI"],
            "education": ["预计2027年硕士毕业"],
            "experience": [],
        }
    )
    result = evaluate(job, resume, DEFAULT_WEIGHTS)
    assert result["components"] == {
        "skills": 35,
        "projects": 0,
        "education": 0,
        "experience": 0,
    }
    assert result["details"]["education"]["status"] == "unknown"
    assert result["details"]["experience"]["status"] == "unknown"
    assert evaluate(job, None, DEFAULT_WEIGHTS)["score"] == 0


def test_work_dates_merge_overlap_and_ignore_internship_and_age():
    assert (
        work_years(["甲公司 2020.01-2022.01 工程师", "乙公司 2021.01-2023.01 工程师"])
        == 3
    )
    assert work_years(["2019.01-2020.01 实习工程师", "年龄28，2018年本科毕业"]) is None
    assert work_years(["5年工作经验"]) == 5


def test_lower_degree_and_partial_tenure_are_not_full_match():
    job = _job(1, description="要求硕士学历，Python").model_copy(
        update={"experience_min_years": 4}
    )
    resume = SimpleNamespace(
        content={"education": ["本科学士"], "experience": ["2年工作经验"]}
    )
    result = evaluate(job, resume, DEFAULT_WEIGHTS)
    assert result["components"]["education"] == 0
    assert result["details"]["education"]["status"] == "known"
    assert result["components"]["experience"] == 10


def test_old_rule_and_history_survive_new_default(tmp_path):
    db, workspace, jobs, service = _services(tmp_path)
    job = _job(1)
    jobs.upsert(workspace.workspace_id, job)
    old_weights = {"responsibilities": 35, "skills": 30, "projects": 25, "bonus": 10}
    old_rule = service.ensure_rule_version(workspace.workspace_id, old_weights)
    old_run = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI",
        job_ids=[job.job_id],
        resume_version=None,
        filters=DesktopJobFilters(),
        rule_version_id=old_rule,
    )
    before = service.page(
        workspace_id=workspace.workspace_id, run_id=old_run, page=1, page_size=10
    )
    new_rule = service.ensure_rule_version(workspace.workspace_id)
    assert new_rule != old_rule
    assert (
        service.weights_for_rule(
            workspace_id=workspace.workspace_id, rule_version_id=old_rule
        )
        == old_weights
    )
    new_run = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI",
        job_ids=[job.job_id],
        resume_version=None,
        filters=DesktopJobFilters(),
        rule_version_id=new_rule,
    )
    new = service.page(
        workspace_id=workspace.workspace_id, run_id=new_run, page=1, page_size=10
    )
    assert set(new["items"][0]["components"]) == set(DEFAULT_WEIGHTS)
    assert new["items"][0]["scoring_version"] == "desktop-v2"
    assert (
        service.page(
            workspace_id=workspace.workspace_id, run_id=old_run, page=1, page_size=10
        )
        == before
    )
    with pytest.raises(ValueError):
        service.ensure_rule_version(
            workspace.workspace_id,
            {"skills": 35, "projects": 30, "education": 15, "experience": 10},
        )


def test_matching_preview_uses_stored_workspace_job_and_requires_auth(tmp_path):
    from fastapi.testclient import TestClient

    from jobfindsme.desktop_api import create_app

    db, workspace, jobs, service = _services(tmp_path)
    job = _job(1)
    jobs.upsert(workspace.workspace_id, job)
    client = TestClient(
        create_app(token="preview-token", database_path=tmp_path / "desktop-jobs.db")
    )
    body = {
        "workspace_id": workspace.workspace_id,
        "job_id": job.job_id,
        "weights": DEFAULT_WEIGHTS,
    }
    assert client.post("/v1/matching-preview", json=body).status_code == 401
    response = client.post(
        "/v1/matching-preview",
        json=body,
        headers={"Authorization": "Bearer preview-token"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["score"] == 0
    assert response.json()["resume_version_id"] is None
    assert set(response.json()["details"]) == set(DEFAULT_WEIGHTS)
    body["workspace_id"] = "other-workspace"
    assert (
        client.post(
            "/v1/matching-preview",
            json=body,
            headers={"Authorization": "Bearer preview-token"},
        ).status_code
        == 404
    )
