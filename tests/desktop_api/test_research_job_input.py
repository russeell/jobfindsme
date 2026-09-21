import pytest

from jobfindsme.importing.repository import JobRepository
from jobfindsme.research.job_input import prepare_job, validate_job_url
from jobfindsme.storage import Database
from jobfindsme.workspaces import WorkspaceService


@pytest.mark.parametrize(
    "url",
    [
        "http://www.liepin.com/job/1",
        "https://u:p@www.liepin.com/job/1",
        "https://www.liepin.com:8443/job/1",
        "https://127.0.0.1",
        "file:///tmp/jd",
        "https://liepin.com.evil.test/",
        "https://www.liepin.com:bad/",
    ],
)
def test_reject_unsafe_research_links(url):
    with pytest.raises(ValueError):
        validate_job_url(url)


def test_tencent_workday_tenant_is_exact():
    url = "https://tencent.wd1.myworkdayjobs.com/Tencent_Careers/job/example"
    assert validate_job_url(url) == url
    for host in ("other.wd1.myworkdayjobs.com", "evil.tencent.wd1.myworkdayjobs.com"):
        with pytest.raises(ValueError):
            validate_job_url(f"https://{host}/")


def test_confirmed_pasted_jd_is_stored_without_fabricated_fetch(tmp_path):
    db = Database(tmp_path / "test.db")
    db.migrate()
    workspace = WorkspaceService(db).create()
    jobs = JobRepository(db)
    result = prepare_job(
        jobs,
        workspace_id=workspace.workspace_id,
        url="https://www.liepin.com/job/123.html",
        title="Python 工程师",
        company="测试公司",
        description=(
            "负责 Python 服务开发与维护，参与检索功能、"
            "接口设计、测试验证与项目文档编写。"
        ),
    )
    assert result["job_id"].startswith("research_")
    assert result["source"]["source_name"] == "用户确认 JD（未独立核验）"
    assert (
        jobs.get(
            workspace_id=workspace.workspace_id, job_id=result["job_id"]
        ).description
        == result["description"]
    )


def test_boss_detail_enriches_existing_job_without_losing_identity(tmp_path):
    from datetime import UTC, datetime

    from jobfindsme.connectors import RawJobRecord
    from jobfindsme.contracts import SourceKind
    from jobfindsme.importing.normalizer import normalize_job
    from jobfindsme.research.job_input import enrich_boss_job

    db = Database(tmp_path / "test.db")
    db.migrate()
    workspace = WorkspaceService(db).create()
    jobs = JobRepository(db)
    url = "https://www.zhipin.com/job_detail/fixture.html"
    old = normalize_job(
        RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="BOSS直聘",
            source_url=url,
            external_id="fixture",
            payload={"title": "旧标题", "apply_url": url},
        )
    )
    assert old.company == "公司未知"
    jobs.upsert(workspace.workspace_id, old)
    detail = dict(
        url=url,
        title="Agent开发工程师",
        company="样例科技",
        location="上海",
        salary="25-35K",
        description="负责 Agent 框架与架构，设计记忆系统、工具调用，构建 RAG 知识库。"
        * 3,
        fetched_at=datetime.now(UTC).isoformat(),
    )
    result = enrich_boss_job(
        jobs, workspace_id=workspace.workspace_id, job_id=old.job_id, **detail
    )
    assert result["job_id"] == old.job_id
    assert result["company"] == "样例科技"
    assert result["locations"] == ["上海"]
    assert result["salary_min_k"] == 25
    assert result["salary_max_k"] == 35
    assert result["source"]["description_source_url"] == url
    assert (
        jobs.get(workspace_id=workspace.workspace_id, job_id=old.job_id).title
        == "Agent开发工程师"
    )
    with pytest.raises(ValueError):
        enrich_boss_job(
            jobs,
            workspace_id=workspace.workspace_id,
            job_id=old.job_id,
            **{**detail, "url": "https://www.zhipin.com/job_detail/other.html"},
        )
    with pytest.raises(LookupError):
        enrich_boss_job(jobs, workspace_id="other", job_id=old.job_id, **detail)


def test_legacy_boss_display_and_unknown_company_identity(tmp_path):
    from jobfindsme.connectors import RawJobRecord
    from jobfindsme.contracts import SourceKind
    from jobfindsme.importing.normalizer import normalize_job
    from jobfindsme.importing.repository import _load_job_payload

    def raw(url):
        return RawJobRecord(
            source_kind=SourceKind.CAREER_SITE,
            source_name="BOSS直聘",
            source_url=url,
            external_id=url,
            payload={"title": "Agent开发工程师", "apply_url": url},
        )

    first = normalize_job(raw("https://www.zhipin.com/job_detail/a.html"))
    second = normalize_job(raw("https://www.zhipin.com/job_detail/b.html"))
    assert first.company == "公司未知"
    assert first.job_id != second.job_id
    old = first.model_copy(
        update={"title": "Agent开发工程师 -K", "company": "BOSS直聘"}
    )
    repaired = _load_job_payload(old.model_dump_json())
    assert repaired.title == "Agent开发工程师"
    assert repaired.company == "公司未知"
    assert repaired.job_id == old.job_id


def test_generic_detail_does_not_overwrite_another_hash_job(tmp_path):
    from jobfindsme.research.job_input import enrich_source_job

    db = Database(tmp_path / "detail.db")
    db.migrate()
    workspace = WorkspaceService(db).create()
    jobs = JobRepository(db)
    url = "https://app.mokahr.com/social-recruitment/zphz/148983#/job/abc"
    old = prepare_job(
        jobs,
        workspace_id=workspace.workspace_id,
        url=url,
        title="工程师",
        company="智谱",
        description="原始岗位描述内容。" * 8,
    )
    detail = dict(
        url=url,
        title="后端工程师",
        company="智谱",
        description="已读取的完整职责与要求。" * 10,
        fetched_at="2026-09-19T12:00:00+00:00",
    )
    result = enrich_source_job(
        jobs, workspace_id=workspace.workspace_id, job_id=old["job_id"], **detail
    )
    assert result["job_id"] == old["job_id"]
    assert result["source"]["detail_level"] == "detail_page"
    detail["url"] = url.replace("/abc", "/def")
    with pytest.raises(ValueError, match="不一致"):
        enrich_source_job(
            jobs, workspace_id=workspace.workspace_id, job_id=old["job_id"], **detail
        )
