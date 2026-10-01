from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobfindsme.connectors import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.repository import JobRepository
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search.jobs import DesktopJobFilters, DesktopJobService
from jobfindsme.search.plans import SearchPlanService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


def _services(tmp_path: Path):
    database = Database(tmp_path / "desktop-jobs.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    jobs = JobRepository(database)
    return database, workspace, jobs, DesktopJobService(database, jobs)


def _job(number: int, *, description: str = "Python FastAPI", location="上海"):
    return normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="猎聘",
            source_url=f"https://www.liepin.com/job/{number}",
            external_id=str(number),
            payload={
                "title": f"AI 应用工程师 {number:03}",
                "company": f"公司 {number:03}",
                "description": description,
                "location": location,
                "salary_min_k": 20,
                "salary_max_k": 35,
                "experience_min_years": 1,
                "experience_max_years": 3,
                "recruitment_track": "social",
                "employment_type": "full_time",
                "apply_url": f"https://www.liepin.com/job/{number}",
            },
        ),
        fetched_at=datetime(2026, 9, 18, tzinfo=UTC),
    )


def test_monthly_salary_presets_overlap_inclusive_and_keep_unknown() -> None:
    def match(job, low, high):
        return DesktopJobService._matches(
            job,
            filters=DesktopJobFilters(
                salary_min_k=low,
                salary_max_k=high,
                salary_mode="overlap",
                unknown_policy="include",
            ),
            read_ids=set(),
        )

    overlap = _job(1).model_copy(update={"salary_min_k": 15, "salary_max_k": 25})
    outside = _job(2).model_copy(update={"salary_min_k": 10, "salary_max_k": 15})
    boundary = _job(3).model_copy(update={"salary_min_k": 10, "salary_max_k": 20})
    unknown = _job(4).model_copy(update={"salary_min_k": None, "salary_max_k": None})
    assert match(overlap, 20, 50)
    assert not match(outside, 20, 50)
    assert match(boundary, 20, 50)
    assert match(boundary, None, 10)
    assert match(overlap, 50, None) is False
    assert match(unknown, 20, 50)

    annual = normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="猎聘",
            source_url="https://www.liepin.com/job/annual",
            external_id="annual",
            payload={
                "title": "年薪岗位",
                "company": "样例",
                "raw_salary_text": "30-50万/年",
                "apply_url": "https://www.liepin.com/job/annual",
            },
        )
    )
    assert annual.salary is not None and annual.salary.period.value == "year"
    assert match(annual, 20, 50)  # annual amount remains unverified monthly


def test_snapshot_pagination_is_stable_without_duplicates_or_gaps(tmp_path) -> None:
    _database, workspace, jobs, service = _services(tmp_path)
    values = [_job(number) for number in range(55)]
    for job in values:
        jobs.upsert(workspace.workspace_id, job)

    run_id = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI 应用工程师",
        job_ids=[job.job_id for job in values],
        resume_version=None,
        filters=DesktopJobFilters(cities=("上海",), unknown_policy="exclude"),
    )
    pages = [
        service.page(
            workspace_id=workspace.workspace_id,
            run_id=run_id,
            page=number,
            page_size=20,
        )
        for number in (1, 2, 3)
    ]
    ids = [item["job"]["job_id"] for page in pages for item in page["items"]]
    assert len(ids) == 55
    assert len(set(ids)) == 55

    late = _job(99)
    jobs.upsert(workspace.workspace_id, late)
    repeated = service.page(
        workspace_id=workspace.workspace_id,
        run_id=run_id,
        page=1,
        page_size=20,
    )
    assert [item["job"]["job_id"] for item in repeated["items"]] == ids[:20]


def test_default_snapshot_scores_each_unique_job_once(tmp_path, monkeypatch) -> None:
    import jobfindsme.search.jobs as jobs_module

    _database, workspace, jobs, service = _services(tmp_path)
    item = _job(1)
    jobs.upsert(workspace.workspace_id, item)
    original = jobs_module.evaluate
    calls = []

    def counted(job, resume, weights):
        calls.append(job.job_id)
        return original(job, resume, weights)

    monkeypatch.setattr(jobs_module, "evaluate", counted)
    service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI 应用工程师",
        job_ids=[item.job_id, item.job_id],
        resume_version=None,
        filters=DesktopJobFilters(),
    )
    assert calls == [item.job_id]


def test_concurrent_source_batches_do_not_lose_jobs(tmp_path) -> None:
    _database, workspace, jobs, service = _services(tmp_path)
    values = [_job(number) for number in range(4)]
    for item in values:
        jobs.upsert(workspace.workspace_id, item)
    run_id = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI 应用工程师",
        job_ids=[],
        resume_version=None,
        filters=DesktopJobFilters(),
    )

    def append(item):
        service.append_snapshot(
            workspace_id=workspace.workspace_id,
            run_id=run_id,
            job_ids=[item.job_id],
            resume_version=None,
        )

    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(append, values))
    page = service.page(
        workspace_id=workspace.workspace_id, run_id=run_id, page=1, page_size=10
    )
    assert {row["job"]["job_id"] for row in page["items"]} == {
        item.job_id for item in values
    }


def test_append_rejects_changed_search_context(tmp_path) -> None:
    _database, workspace, jobs, service = _services(tmp_path)
    item = _job(1)
    jobs.upsert(workspace.workspace_id, item)
    run_id = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI 工程师",
        job_ids=[],
        resume_version=None,
        filters=DesktopJobFilters(cities=("上海",)),
    )
    with pytest.raises(ValueError, match="filters changed"):
        service.append_snapshot(
            workspace_id=workspace.workspace_id,
            run_id=run_id,
            job_ids=[item.job_id],
            resume_version=None,
            expected_intent="AI 工程师",
            expected_filters=DesktopJobFilters(cities=("北京",)),
        )
    assert (
        service.page(
            workspace_id=workspace.workspace_id, run_id=run_id, page=1, page_size=10
        )["total"]
        == 0
    )


def test_updated_job_does_not_replace_old_search_snapshot_jd(tmp_path) -> None:
    _database, workspace, jobs, service = _services(tmp_path)
    original = _job(1, description="Python FastAPI 原始岗位职责")
    jobs.upsert(workspace.workspace_id, original)
    old_run = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="Python",
        job_ids=[original.job_id],
        resume_version=None,
        filters=DesktopJobFilters(),
    )
    updated = _job(1, description="Python FastAPI 更新后岗位职责与更多具体要求" * 3)
    jobs.upsert(workspace.workspace_id, updated)
    assert (
        jobs.get(
            workspace_id=workspace.workspace_id, job_id=original.job_id
        ).content_hash
        == updated.content_hash
    )
    old = service.page(
        workspace_id=workspace.workspace_id, run_id=old_run, page=1, page_size=10
    )["items"][0]
    assert old["job"]["description"] == original.description
    assert old["job"]["content_hash"] == original.content_hash
    assert old["snapshot_status"] == "exact"
    new_run = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="Python",
        job_ids=[original.job_id],
        resume_version=None,
        filters=DesktopJobFilters(),
    )
    new = service.page(
        workspace_id=workspace.workspace_id, run_id=new_run, page=1, page_size=10
    )["items"][0]
    assert new["job"]["description"] == updated.description

    with service.database.connect() as connection:
        connection.execute(
            "UPDATE desktop_search_runs SET job_snapshot_refs_json='{}' WHERE run_id=?",
            (old_run,),
        )
    unknown = service.page(
        workspace_id=workspace.workspace_id, run_id=old_run, page=1, page_size=10
    )["items"][0]
    assert unknown["snapshot_status"] == "unknown"
    assert unknown["score"] is None


def test_unknown_policy_weight_validation_and_resume_ranking(tmp_path) -> None:
    database, workspace, jobs, service = _services(tmp_path)
    profiles = ResumeProfileService(database)
    source = tmp_path / "resume.md"
    source.write_text("# Skills\nPython\n# Projects\nFastAPI 服务", encoding="utf-8")
    draft = profiles.import_resume(
        workspace_id=workspace.workspace_id, source_path=source
    )
    profiles.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=draft.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in draft.facts],
    )
    resume = profiles.current_version(workspace_id=workspace.workspace_id)
    python_job = _job(1, description="Python FastAPI")
    go_job = _job(2, description="Go Kubernetes")
    unknown_city = _job(3, location=None)
    for job in (python_job, go_job, unknown_city):
        jobs.upsert(workspace.workspace_id, job)

    run_id = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI 应用工程师",
        job_ids=[go_job.job_id, python_job.job_id, unknown_city.job_id],
        resume_version=resume,
        filters=DesktopJobFilters(cities=("上海",), unknown_policy="exclude"),
    )
    page = service.page(
        workspace_id=workspace.workspace_id, run_id=run_id, page=1, page_size=10
    )
    assert page["resume_version_id"] == resume.version_id
    assert page["items"][0]["job"]["job_id"] == python_job.job_id
    assert unknown_city.job_id not in {item["job"]["job_id"] for item in page["items"]}

    with pytest.raises(ValueError, match="total 100"):
        service.create_snapshot(
            workspace_id=workspace.workspace_id,
            intent="AI",
            job_ids=[python_job.job_id],
            resume_version=resume,
            filters=DesktopJobFilters(),
            weights={"responsibilities": 1, "skills": 1, "projects": 1, "bonus": 1},
        )


def test_snapshot_uses_the_exact_frozen_rule_version(tmp_path) -> None:
    _database, workspace, jobs, service = _services(tmp_path)
    job = _job(1)
    jobs.upsert(workspace.workspace_id, job)
    frozen = service.ensure_rule_version(
        workspace.workspace_id,
        {"responsibilities": 10, "skills": 70, "projects": 10, "bonus": 10},
    )

    run_id = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent="AI 应用工程师",
        job_ids=[job.job_id],
        resume_version=None,
        filters=DesktopJobFilters(),
        rule_version_id=frozen,
    )
    page = service.page(
        workspace_id=workspace.workspace_id,
        run_id=run_id,
        page=1,
        page_size=10,
    )
    assert page["rule_version_id"] == frozen
    with pytest.raises(ValueError, match="mutually exclusive"):
        service.create_snapshot(
            workspace_id=workspace.workspace_id,
            intent="AI",
            job_ids=[job.job_id],
            resume_version=None,
            filters=DesktopJobFilters(),
            weights={"responsibilities": 35, "skills": 30, "projects": 25, "bonus": 10},
            rule_version_id=frozen,
        )


def test_read_saved_and_applied_are_explicit_independent_and_reversible(
    tmp_path,
) -> None:
    database, workspace, jobs, service = _services(tmp_path)
    job = _job(1)
    jobs.upsert(workspace.workspace_id, job)

    with database.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM job_read_events").fetchone()[0]
            == 0
        )

    service.set_tracking(
        workspace_id=workspace.workspace_id,
        job_id=job.job_id,
        event_type="apply_opened",
    )
    assert (
        service.tracking_states(workspace.workspace_id, [job.job_id])[
            job.job_id
        ].applied
        is False
    )

    service.set_tracking(
        workspace_id=workspace.workspace_id, job_id=job.job_id, event_type="read"
    )
    service.set_tracking(
        workspace_id=workspace.workspace_id, job_id=job.job_id, event_type="saved"
    )
    state = service.set_tracking(
        workspace_id=workspace.workspace_id, job_id=job.job_id, event_type="applied"
    )
    assert (state.read, state.saved, state.applied) == (True, True, True)

    state = service.set_tracking(
        workspace_id=workspace.workspace_id,
        job_id=job.job_id,
        event_type="saved",
        enabled=False,
    )
    assert (state.read, state.saved, state.applied) == (True, False, True)


def test_tracking_migration_preserves_state_but_not_old_impressions(tmp_path) -> None:
    database, workspace, jobs, _service = _services(tmp_path)
    job = _job(1)
    jobs.upsert(workspace.workspace_id, job)
    plan = SearchPlanService(database).create(
        workspace_id=workspace.workspace_id,
        name="legacy",
        target_roles=["AI 应用工程师"],
    )
    now = datetime.now(UTC).isoformat()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO job_states (workspace_id, job_id, state, note, updated_at)
            VALUES (?, ?, 'saved', '', ?)
            """,
            (workspace.workspace_id, job.job_id, now),
        )
        connection.execute(
            """
            INSERT INTO search_job_impressions (
                workspace_id, plan_id, job_id, first_shown_at, last_shown_at,
                shown_count, last_content_hash, last_liveness
            ) VALUES (?, ?, ?, ?, ?, 3, ?, 'active')
            """,
            (
                workspace.workspace_id,
                plan.plan_id,
                job.job_id,
                now,
                now,
                job.content_hash,
            ),
        )
        connection.execute("DROP TABLE job_tracking_events")
        connection.execute("DROP TABLE job_tracking_flags")
        connection.execute(
            "DELETE FROM schema_migrations "
            "WHERE version = '0020_independent_job_tracking'"
        )

    database.migrate()
    with database.connect() as connection:
        migrated = connection.execute(
            "SELECT saved, applied FROM job_tracking_flags WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()
        read_count = connection.execute(
            "SELECT COUNT(*) FROM job_read_events WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()[0]
    assert tuple(migrated) == (1, 0)
    assert read_count == 0


def test_preparation_persists_next_action_without_implicit_application(tmp_path):
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, tracking = _services(tmp_path)
    job = _job(987)
    jobs.upsert(workspace.workspace_id, job)
    preparations = JobPreparationService(database)
    original = preparations.get(workspace.workspace_id, job.job_id)
    assert original["preparation"]["stage"] == "considering"
    assert tracking.list_tracking(workspace_id=workspace.workspace_id) == []
    saved = preparations.save(
        workspace.workspace_id,
        job.job_id,
        stage="considering",
        next_action=" 准备项目介绍 ",
        due_date="2026-10-03",
        note="练习资料",
    )
    assert saved["preparation"]["next_action"] == "准备项目介绍"
    assert not tracking.tracking_states(workspace.workspace_id, [job.job_id])[
        job.job_id
    ].applied
    rows = tracking.list_tracking(workspace_id=workspace.workspace_id)
    assert rows[0]["preparation"]["due_date"] == "2026-10-03"
    restored = JobPreparationService(Database(tmp_path / "desktop-jobs.db"))
    assert restored.get(workspace.workspace_id, job.job_id) == saved


def test_preparation_and_explicit_tracking_stay_consistent(tmp_path):
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, tracking = _services(tmp_path)
    job = _job(988)
    jobs.upsert(workspace.workspace_id, job)
    preparations = JobPreparationService(database)
    tracking.set_tracking(
        workspace_id=workspace.workspace_id, job_id=job.job_id, event_type="saved"
    )
    preparations.save(
        workspace.workspace_id,
        job.job_id,
        stage="interview",
        next_action="练习技术问答",
    )
    flags = tracking.tracking_states(workspace.workspace_id, [job.job_id])[job.job_id]
    assert flags.saved and flags.applied
    tracking.set_tracking(
        workspace_id=workspace.workspace_id, job_id=job.job_id, event_type="applied"
    )
    assert (
        preparations.get(workspace.workspace_id, job.job_id)["preparation"]["stage"]
        == "interview"
    )
    preparations.save(workspace.workspace_id, job.job_id, stage="closed")
    assert tracking.tracking_states(workspace.workspace_id, [job.job_id])[
        job.job_id
    ].applied
    tracking.set_tracking(
        workspace_id=workspace.workspace_id,
        job_id=job.job_id,
        event_type="applied",
        enabled=False,
    )
    assert (
        preparations.get(workspace.workspace_id, job.job_id)["preparation"]["stage"]
        == "considering"
    )
    other = WorkspaceService(database).create()
    with pytest.raises(LookupError):
        preparations.save(other.workspace_id, job.job_id, stage="offer")
    with pytest.raises(ValueError):
        preparations.save(
            workspace.workspace_id, job.job_id, stage="interview", due_date="tomorrow"
        )
