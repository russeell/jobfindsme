from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobfindsme.connectors import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.desktop_jobs import DesktopJobFilters, DesktopJobService
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.repository import JobRepository
from jobfindsme.profiles.service import ResumeProfileService
from jobfindsme.search_plans import SearchPlanService
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
