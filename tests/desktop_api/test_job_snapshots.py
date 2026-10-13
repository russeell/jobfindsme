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


@pytest.mark.parametrize(
    ("profile", "description", "updates", "matches"),
    [
        ("student", "接受在校生，每周到岗三天", {}, True),
        ("student", "不接受在校生", {}, False),
        ("student", "Python开发", {"employment_type": "internship"}, True),
        ("graduate", "接受应届毕业生", {}, True),
        ("graduate", "不招应届生", {"recruitment_track": "campus"}, False),
        ("graduate", "Python开发", {"recruitment_track": "campus"}, True),
        (
            "graduate",
            "Python开发",
            {"recruitment_track": "campus", "employment_type": "internship"},
            False,
        ),
        ("graduate", "本科毕业生，五年经验", {}, False),
        (
            "graduate",
            "Python开发",
            {"experience_min_years": 0, "experience_max_years": 0},
            False,
        ),
        (
            "student",
            "Python开发",
            {"experience_min_years": None, "experience_max_years": None},
            False,
        ),
    ],
)
def test_student_and_graduate_filters_need_positive_source_evidence(
    profile, description, updates, matches
):
    from jobfindsme.contracts import EmploymentType, RecruitmentTrack

    values = dict(updates)
    if "employment_type" in values:
        values["employment_type"] = EmploymentType(values["employment_type"])
    if "recruitment_track" in values:
        values["recruitment_track"] = RecruitmentTrack(values["recruitment_track"])
    job = _job(701, description=description).model_copy(update=values)
    assert (
        DesktopJobService._matches(
            job, filters=DesktopJobFilters(experience_profile=profile), read_ids=set()
        )
        is matches
    )


def test_experience_profile_survives_preflight_snapshot_and_refilter(tmp_path):
    from jobfindsme.desktop_api.app import DesktopSearchFilters
    from jobfindsme.search.intent import parse_intent

    _db, workspace, jobs, service = _services(tmp_path)
    student = _job(702, description="Python 实习，接受在校生")
    graduate = _job(703, description="Python 应届生，提供全职岗位")
    senior = _job(704, description="Python 工程师，要求五年经验")
    for job in (student, graduate, senior):
        jobs.upsert(workspace.workspace_id, job)
    api_filters = DesktopSearchFilters(
        experience_profile="graduate", employment_type="full_time"
    )
    parsed = parse_intent(
        "Python", filters=DesktopJobFilters(**api_filters.model_dump())
    )
    assert parsed.payload()["filters"]["experience_profile"] == "graduate"
    run_id = service.create_snapshot(
        workspace_id=workspace.workspace_id,
        intent=parsed.query,
        job_ids=[student.job_id, graduate.job_id, senior.job_id],
        resume_version=None,
        filters=parsed.filters,
    )
    page = service.page(
        workspace_id=workspace.workspace_id, run_id=run_id, page=1, page_size=10
    )
    assert [item["job"]["job_id"] for item in page["items"]] == [graduate.job_id]
    from fastapi.testclient import TestClient

    from jobfindsme.desktop_api.app import create_app

    client = TestClient(create_app(token="test-secret", database_path=_db.path))
    headers = {"Authorization": "Bearer test-secret"}
    endpoint = f"/v1/search-runs/{run_id}/refilter"
    student_page = client.post(
        endpoint,
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "filters": {"experience_profile": "student"},
        },
    )
    assert student_page.status_code == 200, student_page.text
    assert [item["job"]["job_id"] for item in student_page.json()["items"]] == [
        student.job_id
    ]
    reset = client.post(
        endpoint,
        headers=headers,
        json={"workspace_id": workspace.workspace_id, "filters": {}},
    )
    assert reset.status_code == 200 and reset.json()["total"] == 3
    part_time = client.post(
        endpoint,
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "filters": {"employment_type": "part_time"},
        },
    )
    assert part_time.status_code == 200 and part_time.json()["total"] == 0
    with pytest.raises(ValueError):
        DesktopJobFilters(experience_profile="unsupported").validate()


def test_interactive_work_type_excludes_unknown_but_legacy_snapshots_keep_policy():
    from jobfindsme.contracts import EmploymentType

    unknown = _job(801).model_copy(update={"employment_type": EmploymentType.UNKNOWN})
    part_time = _job(802).model_copy(
        update={"employment_type": EmploymentType.PART_TIME}
    )
    full_time = _job(803)
    strict = DesktopJobFilters(
        employment_type="part_time", require_known_employment=True
    )
    assert not DesktopJobService._matches(unknown, filters=strict, read_ids=set())
    assert not DesktopJobService._matches(full_time, filters=strict, read_ids=set())
    assert DesktopJobService._matches(part_time, filters=strict, read_ids=set())
    legacy = DesktopJobFilters(employment_type="part_time")
    assert DesktopJobService._matches(unknown, filters=legacy, read_ids=set())
    assert DesktopJobService._matches(
        unknown, filters=DesktopJobFilters(), read_ids=set()
    )


def test_application_materials_survive_resume_changes_and_require_explicit_send(
    tmp_path,
):
    from jobfindsme.profiles.service import ResumeProfileService
    from jobfindsme.resume_editor import ResumeEditorService
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, tracking = _services(tmp_path)
    job = _job(990)
    jobs.upsert(workspace.workspace_id, job)
    service = JobPreparationService(database)
    profiles = ResumeProfileService(database)
    file = tmp_path / "synthetic.md"
    file.write_text("# Skills\nPython\n# Projects\n虚构离线测试项目")
    draft = profiles.import_resume(
        workspace_id=workspace.workspace_id, source_path=file
    )
    profiles.confirm_profile(
        workspace_id=workspace.workspace_id,
        profile_id=draft.profile_id,
        accepted_fact_ids=[f.fact_id for f in draft.facts],
    )
    version = profiles.current_version(workspace_id=workspace.workspace_id)
    payload = dict(
        workspace_id=workspace.workspace_id,
        job_id=job.job_id,
        record_id="local-test",
        resume_version_id=version.version_id,
        message="虚构测试开场白",
    )
    service.save(
        workspace.workspace_id, job.job_id, stage="considering", next_action="下次跟进"
    )
    for status in ["prepared", "opened"]:
        service.record_application(**payload, status=status)
        assert not tracking.list_tracking(workspace_id=workspace.workspace_id)[0][
            "tracking"
        ]["applied"]
    service.record_application(**payload, status="resume_sent")
    assert tracking.list_tracking(workspace_id=workspace.workspace_id)[0]["tracking"][
        "applied"
    ]
    assert (
        service.get(workspace.workspace_id, job.job_id)["preparation"]["stage"]
        == "applied"
    )
    assert (
        service.get(workspace.workspace_id, job.job_id)["preparation"]["next_action"]
        == "下次跟进"
    )
    ResumeEditorService(database).save_edit(
        workspace_id=workspace.workspace_id,
        base_version_id=version.version_id,
        content={**version.content, "skills": ["Python", "SQL"]},
    )
    stored = service.list_applications(workspace.workspace_id)[0]
    assert stored["resume_version_id"] == version.version_id
    with pytest.raises(ValueError, match="不能覆盖"):
        service.record_application(
            **{**payload, "message": "changed"}, status="prepared"
        )
    with pytest.raises(ValueError, match="workspace"):
        service.record_application(
            **{**payload, "record_id": "other", "resume_version_id": "wrong-workspace"},
            status="prepared",
        )
    assert len(service.list_applications(workspace.workspace_id)) == 1
    assert service.list_applications("other-workspace") == []
    from fastapi.testclient import TestClient

    from jobfindsme.desktop_api.app import create_app

    client = TestClient(
        create_app(token="fixture-token", database_path=tmp_path / "desktop-jobs.db")
    )
    headers = {"Authorization": "Bearer fixture-token"}
    assert (
        client.get(
            "/v1/application-records", params={"workspace_id": workspace.workspace_id}
        ).status_code
        == 401
    )
    response = client.get(
        "/v1/application-records",
        headers=headers,
        params={"workspace_id": workspace.workspace_id},
    )
    assert response.json()[0]["resume_version_id"] == version.version_id
    response = client.post(
        "/v1/application-records",
        headers=headers,
        json={**payload, "record_id": "api-new", "status": "opened"},
    )
    assert response.status_code == 200
    response = client.post(
        "/v1/application-records",
        headers=headers,
        json={
            **payload,
            "record_id": "api-bad",
            "status": "resume_sent",
            "resume_version_id": None,
        },
    )
    assert response.status_code == 400
    # The saved application itself links interview materials, without a DB patch.
    assert (
        service.get(workspace.workspace_id, job.job_id)["preparation"][
            "resume_version_id"
        ]
        == version.version_id
    )
    response = client.get(
        "/v1/research-agent/resume",
        headers=headers,
        params={"workspace_id": workspace.workspace_id, "job_id": job.job_id},
    )
    assert response.status_code == 200
    assert response.json()["source_version_id"] == version.version_id
    matched = client.post(
        "/v1/matching-preview",
        headers=headers,
        json={
            "workspace_id": workspace.workspace_id,
            "job_id": job.job_id,
            "resume_version_id": version.version_id,
            "weights": {
                "skills": 35,
                "projects": 30,
                "education": 15,
                "experience": 20,
            },
        },
    )
    assert matched.status_code == 200
    assert matched.json()["resume_version_id"] == version.version_id
    assert (
        client.post(
            "/v1/matching-preview",
            headers=headers,
            json={
                "workspace_id": workspace.workspace_id,
                "job_id": job.job_id,
                "resume_version_id": "other-workspace-version",
                "weights": {
                    "skills": 35,
                    "projects": 30,
                    "education": 15,
                    "experience": 20,
                },
            },
        ).status_code
        == 400
    )
    response = client.get(
        "/v1/research-agent/resume",
        headers=headers,
        params={"workspace_id": workspace.workspace_id},
    )
    assert response.json()["source_version_id"] != version.version_id
    selected = client.get(
        "/v1/research-agent/resume",
        headers=headers,
        params={
            "workspace_id": workspace.workspace_id,
            "resume_version_id": version.version_id,
        },
    )
    assert selected.status_code == 200
    assert selected.json()["source_version_id"] == version.version_id
    assert "basic_information" not in selected.json()["content"]
    for workspace_id, version_id in [
        ("other", version.version_id),
        (workspace.workspace_id, "missing"),
    ]:
        assert (
            client.get(
                "/v1/research-agent/resume",
                headers=headers,
                params={"workspace_id": workspace_id, "resume_version_id": version_id},
            ).status_code
            == 404
        )
    assert (
        client.get(
            "/v1/research-agent/resume",
            headers=headers,
            params={"workspace_id": "other", "job_id": job.job_id},
        ).status_code
        == 404
    )


def test_preparing_new_materials_keeps_legacy_applied_state(tmp_path) -> None:
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, search = _services(tmp_path)
    job = _job(912)
    jobs.upsert(workspace.workspace_id, job)
    search.set_tracking(
        workspace_id=workspace.workspace_id, job_id=job.job_id, event_type="applied"
    )
    service = JobPreparationService(database)
    assert (
        service.get(workspace.workspace_id, job.job_id)["preparation"]["stage"]
        == "applied"
    )
    service.record_application(
        workspace.workspace_id,
        job.job_id,
        record_id="new-materials",
        resume_version_id=None,
        message="虚构开场白",
        status="prepared",
    )
    preparation = service.get(workspace.workspace_id, job.job_id)["preparation"]
    assert preparation["stage"] == "applied"
    service.save(
        workspace.workspace_id,
        job.job_id,
        stage=preparation["stage"],
        next_action="准备项目介绍",
    )
    assert search.tracking_states(workspace.workspace_id, [job.job_id])[
        job.job_id
    ].applied


def test_application_record_trash_is_scoped_reversible_and_preserves_tracking(tmp_path):
    from fastapi.testclient import TestClient

    from jobfindsme.desktop_api.app import create_app
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, tracking = _services(tmp_path)
    job = _job(991)
    jobs.upsert(workspace.workspace_id, job)
    service = JobPreparationService(database)
    row = service.record_application(
        workspace.workspace_id,
        job.job_id,
        record_id="trash-fixture",
        resume_version_id=None,
        message="虚构话术",
        status="opened",
    )
    service.save(
        workspace.workspace_id, job.job_id, stage="applied", next_action="保持跟进"
    )
    before = tracking.list_tracking(workspace_id=workspace.workspace_id)
    client = TestClient(
        create_app(token="fixture-token", database_path=tmp_path / "desktop-jobs.db")
    )
    headers = {"Authorization": "Bearer fixture-token"}
    params = {
        "workspace_id": workspace.workspace_id,
        "job_id": job.job_id,
        "deleted": True,
    }
    url = "/v1/application-records/trash-fixture"
    assert client.patch(url, params=params).status_code == 401
    assert (
        client.patch(
            url, headers=headers, params={**params, "workspace_id": "elsewhere"}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            url, headers=headers, params={**params, "job_id": "wrong"}
        ).status_code
        == 404
    )
    assert client.patch(url, headers=headers, params=params).status_code == 200
    assert service.list_applications(workspace.workspace_id) == []
    assert (
        service.list_applications(workspace.workspace_id, deleted=True)[0]["message"]
        == row["message"]
    )
    with pytest.raises(ValueError, match="已删除"):
        service.record_application(
            workspace.workspace_id,
            job.job_id,
            record_id="trash-fixture",
            resume_version_id=None,
            message="不得复活",
            status="prepared",
        )
    assert (
        client.patch(
            url, headers=headers, params={**params, "deleted": False}
        ).status_code
        == 200
    )
    assert len(service.list_applications(workspace.workspace_id)) == 1
    assert service.list_applications(workspace.workspace_id, deleted=True) == []
    assert tracking.list_tracking(workspace_id=workspace.workspace_id) == before
    assert (
        service.get(workspace.workspace_id, job.job_id)["preparation"]["next_action"]
        == "保持跟进"
    )


@pytest.mark.parametrize("applied", [False, True])
def test_next_action_can_be_created_without_preparation_and_rejects_stale_creates(
    tmp_path, applied
):
    from fastapi.testclient import TestClient

    from jobfindsme.desktop_api.app import create_app
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, tracking = _services(tmp_path)
    job = _job(998)
    jobs.upsert(workspace.workspace_id, job)
    tracking.set_tracking(
        workspace_id=workspace.workspace_id,
        job_id=job.job_id,
        event_type="applied" if applied else "saved",
    )
    flags = tracking.tracking_states(workspace.workspace_id, [job.job_id])
    client = TestClient(create_app(token="fixture-token", database_path=database.path))
    headers = {"Authorization": "Bearer fixture-token"}
    url = f"/v1/jobs/{job.job_id}/next-action"
    payload = dict(
        workspace_id=workspace.workspace_id,
        expected_updated_at=None,
        next_action=" 跟进投递 " if applied else " 准备面试 ",
        due_date="2026-10-13",
    )
    assert client.patch(url, json=payload).status_code == 401
    assert client.patch(url, headers=headers, json=payload).status_code == 200
    assert client.patch(url, headers=headers, json=payload).status_code == 409
    service = JobPreparationService(database)
    before = service.get(workspace.workspace_id, job.job_id)
    preparation = before["preparation"]
    assert preparation["stage"] == ("applied" if applied else "considering")
    assert preparation["next_action"] == payload["next_action"].strip()
    assert preparation["resume_version_id"] is None and preparation["note"] == ""
    # Rescheduling only the reminder keeps the rest of the opportunity unchanged.
    response = client.patch(
        url,
        headers=headers,
        json={
            **payload,
            "expected_updated_at": preparation["updated_at"],
            "due_date": "2026-10-14",
        },
    )
    assert response.status_code == 200
    after = response.json()
    assert after["preparation"]["due_date"] == "2026-10-14"
    assert after["job"] == before["job"]
    assert tracking.tracking_states(workspace.workspace_id, [job.job_id]) == flags
    assert (
        JobPreparationService(Database(database.path)).get(
            workspace.workspace_id, job.job_id
        )
        == after
    )


def test_next_action_completion_undo_is_scoped_atomic_and_preserves_application(
    tmp_path,
):
    from fastapi.testclient import TestClient

    from jobfindsme.desktop_api.app import create_app
    from jobfindsme.search.preparation import JobPreparationService

    database, workspace, jobs, tracking = _services(tmp_path)
    job = _job(997)
    jobs.upsert(workspace.workspace_id, job)
    service = JobPreparationService(database)
    initial = service.save(
        workspace.workspace_id,
        job.job_id,
        stage="interview",
        next_action="复习虚构项目",
        due_date="2026-10-11",
        note="保留备注",
    )["preparation"]
    flags = tracking.tracking_states(workspace.workspace_id, [job.job_id])
    client = TestClient(create_app(token="fixture-token", database_path=database.path))
    headers = {"Authorization": "Bearer fixture-token"}
    url = f"/v1/jobs/{job.job_id}/next-action"
    payload = dict(
        workspace_id=workspace.workspace_id,
        expected_updated_at=initial["updated_at"],
        next_action="",
        due_date=None,
    )
    assert client.patch(url, json=payload).status_code == 401
    assert (
        client.patch(
            url, headers=headers, json={**payload, "workspace_id": "other"}
        ).status_code
        == 404
    )
    response = client.patch(url, headers=headers, json=payload)
    assert response.status_code == 200
    completed = response.json()["preparation"]
    assert completed["next_action"] == "" and completed["due_date"] is None
    for key in ("stage", "note", "resume_version_id"):
        assert completed[key] == initial[key]
    assert tracking.tracking_states(workspace.workspace_id, [job.job_id]) == flags
    assert client.patch(url, headers=headers, json=payload).status_code == 409
    undo = {
        **payload,
        "expected_updated_at": completed["updated_at"],
        "next_action": initial["next_action"],
        "due_date": initial["due_date"],
    }
    restored = client.patch(url, headers=headers, json=undo)
    assert restored.status_code == 200
    assert restored.json()["preparation"]["next_action"] == initial["next_action"]
    assert restored.json()["preparation"]["due_date"] == initial["due_date"]
    # A later user edit wins over stale completion or undo, including its note/stage.
    fresh = service.save(
        workspace.workspace_id,
        job.job_id,
        stage="offer",
        next_action="核对薪资",
        due_date="2026-10-15",
        note="新备注",
    )
    assert client.patch(url, headers=headers, json=undo).status_code == 409
    assert service.get(workspace.workspace_id, job.job_id) == fresh
    assert (
        JobPreparationService(Database(database.path)).get(
            workspace.workspace_id, job.job_id
        )
        == fresh
    )


@pytest.mark.parametrize("list_level", ["list_card", "structured_source"])
def test_recent_full_jd_survives_unchanged_list_refresh_but_not_expiry(
    tmp_path, list_level
):
    from datetime import timedelta

    from jobfindsme.contracts import JobDetailLevel

    db, workspace, jobs, service = _services(tmp_path)
    base = _job(980)
    base = base.model_copy(
        update={
            "source": base.source.model_copy(
                update={"detail_level": JobDetailLevel(list_level)}
            )
        }
    )
    at = base.source.fetched_at
    detail = base.model_copy(
        update={
            "description": "负责 Python 接口开发，需具备完整项目测试经验。",
            "content_hash": "detail-content-hash-980",
            "source": base.source.model_copy(
                update={
                    "detail_level": JobDetailLevel.DETAIL_PAGE,
                    "description_source_url": base.apply_url,
                    "description_fetched_at": at,
                }
            ),
        }
    )
    jobs.upsert(workspace.workspace_id, detail)
    fresh = base.model_copy(
        update={
            "source": base.source.model_copy(
                update={"fetched_at": at + timedelta(minutes=2)}
            )
        }
    )
    jobs.upsert(workspace.workspace_id, fresh)
    saved = jobs.get(workspace_id=workspace.workspace_id, job_id=base.job_id)
    assert saved.description == detail.description
    assert saved.source.description_fetched_at == at
    # The newer observation is still recorded separately.
    assert (
        jobs.source_records(workspace_id=workspace.workspace_id, job_id=base.job_id)[
            0
        ].observed_at
        == fresh.source.fetched_at
    )
    changed = fresh.model_copy(update={"title": "新的岗位职责"})
    jobs.upsert(workspace.workspace_id, changed)
    assert (
        jobs.get(workspace_id=workspace.workspace_id, job_id=base.job_id).title
        == changed.title
    )
    # Expired cached detail can no longer mask a new list observation.
    jobs.upsert(
        workspace.workspace_id,
        detail.model_copy(
            update={
                "source": detail.source.model_copy(
                    update={"fetched_at": at + timedelta(minutes=3)}
                )
            }
        ),
    )
    expired = base.model_copy(
        update={
            "source": base.source.model_copy(
                update={"fetched_at": at + timedelta(minutes=31)}
            )
        }
    )
    jobs.upsert(workspace.workspace_id, expired)
    assert jobs.get(
        workspace_id=workspace.workspace_id, job_id=base.job_id
    ).source.detail_level is JobDetailLevel(list_level)
