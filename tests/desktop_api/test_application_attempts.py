from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from jobfindsme.connectors import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.importing.repository import JobRepository
from jobfindsme.search.application_attempts import (
    ApplicationAttemptService,
    boss_job_id,
)
from jobfindsme.search.preparation import JobPreparationService
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


@pytest.fixture
def materials(tmp_path):
    database = Database(tmp_path / "applications.db")
    database.migrate()
    workspace = WorkspaceService(database).create()
    url = "https://www.zhipin.com/job_detail/fictional-job.html"
    job = normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="BOSS直聘",
            source_url=url,
            external_id="fictional-job",
            payload={"title": "示例工程师", "company": "虚构公司", "apply_url": url},
        ),
        fetched_at=datetime.now(UTC),
    )
    JobRepository(database).upsert(workspace_id=workspace.workspace_id, job=job)
    preparation = JobPreparationService(database)
    row = preparation.record_application(
        workspace.workspace_id,
        job.job_id,
        record_id="draft",
        resume_version_id=None,
        message="您好，这是虚构测试话术，不会发给真实企业。",
        status="prepared",
    )
    service = ApplicationAttemptService(database)
    payload = dict(
        workspace_id=workspace.workspace_id,
        job_id=job.job_id,
        record_id=row["record_id"],
        expected_updated_at=row["updated_at"],
        target_url=url,
        title=job.title,
        company=job.company,
        file_name=None,
        file_sha256=None,
    )
    return database, service, preparation, payload


def test_reserved_materials_are_exact_and_locked(materials):
    _, service, preparation, payload = materials
    attempt = service.begin(**payload)
    assert attempt["resume_version_id"] is None
    assert attempt["message"] == "您好，这是虚构测试话术，不会发给真实企业。"
    with pytest.raises(ValueError, match="锁定"):
        preparation.record_application(
            payload["workspace_id"],
            payload["job_id"],
            record_id=attempt["record_id"],
            resume_version_id=None,
            message="覆盖",
            status="prepared",
        )
    with pytest.raises(LookupError):
        service.begin(**{**payload, "job_id": "other-job"})


def test_concurrent_confirm_only_reserves_once(materials):
    _, service, _, payload = materials

    def reserve(_):
        try:
            return service.begin(**payload)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(row is not None for row in pool.map(reserve, range(2))) == 1
    assert len(service.list(payload["workspace_id"], payload["job_id"])) == 1


@pytest.mark.parametrize("write_started", [False, True])
def test_restart_does_not_retry_or_claim_delivery(materials, write_started):
    _, service, _, payload = materials
    attempt = service.begin(**payload)
    service.update(attempt["attempt_id"], phase="contact", write_started=write_started)
    service.recover()
    row = service.list(payload["workspace_id"], payload["job_id"])[0]
    assert row["state"] == ("uncertain" if write_started else "cancelled")
    assert not row["message_confirmed"] and not row["resume_confirmed"]
    if write_started:
        with pytest.raises(ValueError, match="重复"):
            service.begin(**payload)


def test_no_receipt_no_applied_and_no_retry(materials):
    database, service, preparation, payload = materials
    attempt = service.begin(**payload)
    with pytest.raises(ValueError, match="回执"):
        service.update(attempt["attempt_id"], phase="finished", state="completed")
    service.update(attempt["attempt_id"], phase="message", write_started=True)
    final = service.update(attempt["attempt_id"], phase="stopped", state="cancelled")
    assert final["state"] == "uncertain"
    preparation.set_application_deleted(
        payload["workspace_id"], payload["job_id"], attempt["record_id"], True
    )
    with pytest.raises(ValueError, match="重复"):
        service.begin(**payload)  # hiding a record cannot defeat deduplication
    with database.connect() as db:
        assert not db.execute(
            "SELECT 1 FROM job_tracking_flags WHERE applied=1"
        ).fetchone()


def test_no_attachment_only_message_confirmation(materials):
    database, service, _, payload = materials
    attempt = service.begin(**payload)
    with pytest.raises(ValueError):
        service.update(
            attempt["attempt_id"],
            phase="resume",
            resume_confirmed=True,
            write_started=True,
            message_confirmed=True,
        )
    service.update(
        attempt["attempt_id"],
        phase="message",
        write_started=True,
        message_confirmed=True,
    )
    final = service.update(attempt["attempt_id"], phase="finished", state="completed")
    assert final["message_confirmed"] and not final["resume_confirmed"]
    with database.connect() as db:
        assert not db.execute(
            "SELECT 1 FROM job_tracking_flags WHERE applied=1"
        ).fetchone()


def test_cooldown_and_material_cas(materials):
    database, service, _, payload = materials
    with pytest.raises(ValueError, match="变化"):
        service.begin(**{**payload, "expected_updated_at": "stale"})
    attempt = service.begin(**payload)
    service.update(attempt["attempt_id"], phase="stopped", state="failed")
    with pytest.raises(ValueError, match="一分钟"):
        service.begin(**payload)
    with database.connect() as db:
        db.execute(
            "UPDATE application_attempts SET created_at=?",
            ((datetime.now(UTC) - timedelta(minutes=2)).isoformat(),),
        )
    assert service.begin(**payload)["attempt_id"] != attempt["attempt_id"]


def test_confirmed_manual_record_also_blocks_automatic_resend(materials):
    _, service, preparation, payload = materials
    preparation.record_application(
        payload["workspace_id"],
        payload["job_id"],
        record_id="manual-confirmed",
        resume_version_id=None,
        message="用户自行沟通过的招呼语",
        status="contacted",
    )
    with pytest.raises(ValueError, match="沟通记录"):
        service.begin(**payload)


def test_persisted_platform_challenge_blocks_new_reservations(materials):
    from jobfindsme.sources.desktop import DesktopSourceService

    database, service, _, payload = materials
    sources = DesktopSourceService(database)
    sources.record_runtime_failure(
        source_id="boss", failure="risk_control", notes="虚构风控样例"
    )
    with database.connect() as db:
        db.execute(
            "UPDATE desktop_source_capabilities SET session_status='blocked' "
            "WHERE source_id='boss'"
        )
    with pytest.raises(ValueError, match="暂停"):
        service.begin(**payload)
    assert service.list(payload["workspace_id"], payload["job_id"]) == []


def test_attachment_receipt_updates_tracking_once_and_preserves_follow_up(
    materials, tmp_path
):
    from jobfindsme.profiles.service import ResumeProfileService

    database, service, preparation, payload = materials
    source = tmp_path / "fictional.md"
    source.write_text("# 专业技能\nPython\n# 项目经历\n虚构项目：开发了示例接口。")
    profiles = ResumeProfileService(database)
    draft = profiles.import_resume(
        workspace_id=payload["workspace_id"], source_path=source
    )
    profiles.confirm_profile(
        workspace_id=payload["workspace_id"],
        profile_id=draft.profile_id,
        accepted_fact_ids=[f.fact_id for f in draft.facts],
    )
    version = profiles.current_version(workspace_id=payload["workspace_id"])
    row = preparation.record_application(
        payload["workspace_id"],
        payload["job_id"],
        record_id="with-file",
        resume_version_id=version.version_id,
        message="虚构招呼语",
        status="prepared",
    )
    preparation.save(
        payload["workspace_id"],
        payload["job_id"],
        stage="considering",
        next_action="下周复习",
        due_date="2026-10-16",
        note="保留笔记",
    )
    attempt = service.begin(
        **{
            **payload,
            "record_id": row["record_id"],
            "expected_updated_at": row["updated_at"],
            "file_name": "简历.pdf",
            "file_sha256": "a" * 64,
        }
    )
    preparation.save(
        payload["workspace_id"],
        payload["job_id"],
        stage="interview",
        next_action="下周复习",
        due_date="2026-10-16",
        note="保留笔记",
    )
    service.update(
        attempt["attempt_id"],
        phase="message",
        write_started=True,
        message_confirmed=True,
    )
    service.update(attempt["attempt_id"], phase="resume", resume_confirmed=True)
    service.update(attempt["attempt_id"], phase="finished", state="completed")
    saved = preparation.get(payload["workspace_id"], payload["job_id"])["preparation"]
    assert (saved["stage"], saved["next_action"], saved["note"]) == (
        "interview",
        "下周复习",
        "保留笔记",
    )
    with database.connect() as db:
        assert db.execute("SELECT applied FROM job_tracking_flags").fetchone()[0] == 1
        assert (
            db.execute(
                "SELECT count(*) FROM job_tracking_events "
                "WHERE event_type='applied' AND enabled=1"
            ).fetchone()[0]
            == 1
        )
    with pytest.raises(ValueError, match="结束"):
        service.update(attempt["attempt_id"], phase="message", message_confirmed=False)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.zhipin.com/job_detail/a.html",
        "https://zhipin.com.evil.com/job_detail/a.html",
        "https://www.zhipin.com/web/geek/chat",
        "https://user@www.zhipin.com/job_detail/a.html",
    ],
)
def test_target_requires_exact_boss_job(url):
    with pytest.raises(ValueError):
        boss_job_id(url)
