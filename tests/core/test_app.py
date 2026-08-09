import ast
from pathlib import Path

from jobfindsme.contracts import (
    DiscoverySource,
    SearchRefreshMode,
    SourceRunStatus,
)
from jobfindsme.core import jobfindsmecore
from jobfindsme.importing.parsers import parse_json
from jobfindsme.importing.service import ImportSummary


def test_core_composes_workspace_and_plan_use_cases(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("My Search")

    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="杭州 AI",
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )

    assert core.list_workspaces() == [workspace]
    assert core.list_search_plans(workspace.workspace_id) == [plan]


def test_core_does_not_import_adapter_frameworks() -> None:
    core_dir = Path(__file__).parents[2] / "src" / "jobfindsme" / "core"
    forbidden = {"fastapi", "mcp", "agents", "flask", "typer", "click"}

    for path in core_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert imports.isdisjoint(forbidden), path


def test_core_matches_imported_jobs_without_an_adapter_framework(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("求职")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="杭州AI",
        target_roles=["AI应用工程师"],
        locations=["杭州"],
    )
    records = parse_json(
        """
        [{
          "id": "1",
          "title": "AI应用工程师",
          "company": "示例科技",
          "location": "杭州",
          "description": "Python RAG Agent",
          "url": "https://example.com/jobs/1"
        }]
        """,
        source_name="fixture",
    )
    core.job_imports.import_records(workspace.workspace_id, records)

    matches = core.match_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
    )

    assert [match.job.external_id for match in matches] == ["1"]


def test_core_configures_and_reuses_active_search_without_ids(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")

    first = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海"],
    )
    second = core.configure_search(
        target_roles=["RAG工程师"],
        locations=["杭州"],
    )

    assert second.workspace.workspace_id == first.workspace.workspace_id
    assert second.plan.plan_id == first.plan.plan_id
    assert second.plan.target_roles == ("RAG工程师",)
    assert isinstance(core.search_jobs(), list)  # may be empty or have live results


def test_core_passes_confirmed_profile_into_matching(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configuration = core.configure_search(target_roles=["AI应用工程师"])
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG", encoding="utf-8")
    profile = core.import_resume(source_path=resume)
    core.confirm_profile(
        profile_id=profile.profile_id,
        accepted_fact_ids=[fact.fact_id for fact in profile.facts],
    )
    records = parse_json(
        """
        [
          {
            "id": "python",
            "title": "AI应用工程师",
            "company": "甲公司",
            "description": "Python RAG",
            "url": "https://example.com/python"
          },
          {
            "id": "java",
            "title": "AI应用工程师",
            "company": "乙公司",
            "description": "Java Spring",
            "url": "https://example.com/java"
          }
        ]
        """,
        source_name="fixture",
    )
    core.job_imports.import_records(configuration.workspace.workspace_id, records)

    matches = core.match_jobs()

    # v0.4: filter-only, no BM25 ranking — both jobs pass hard filter.
    # Order is deterministic and owned by the server.
    external_ids = {match.job.external_id for match in matches}
    assert external_ids == {"python", "java"}
    # Both jobs carry extracted_signals
    for match in matches:
        assert match.evidence.extracted_signals
        assert "required_skills" in match.evidence.extracted_signals


def test_updating_search_constraints_preserves_sources_unless_explicitly_cleared(
    tmp_path,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="本地岗位",
                path=str(tmp_path / "jobs.json"),
            ),
        ),
    )

    updated = core.configure_search(target_roles=["RAG工程师"])
    cleared = core.configure_search(target_roles=["RAG工程师"], sources=())

    assert len(updated.sources) == 1
    assert cleared.sources == ()
    assert updated.plan.plan_id == configured.plan.plan_id


def test_updating_catalog_plan_refreshes_primary_role_query(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海"],
    )

    updated = core.configure_search(
        target_roles=["RAG工程师", "Agent工程师"],
        locations=["上海"],
    )

    assert all(item.source.catalog_managed for item in configured.sources)
    assert {item.source.query for item in updated.sources} == {"RAG工程师"}


def test_partial_browser_snapshot_never_closes_absent_jobs(
    tmp_path,
    monkeypatch,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="boss_cdp",
                source_name="BOSS直聘",
                query="AI应用工程师",
            ),
        ),
    )
    source = configured.sources[0].source

    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._CDPSession.minimize_windows",
        lambda: None,
    )
    monkeypatch.setattr(
        core.discovery,
        "discover",
        lambda **_: (ImportSummary(0, 0, 0, ()),),
    )

    def fail_if_closed(**_: object) -> None:
        raise AssertionError("partial browser snapshots cannot close absent jobs")

    monkeypatch.setattr(core.jobs, "mark_missing_closed", fail_if_closed)

    result = core.search._discover_sources(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        sources=(source,),
    )

    assert result[0].status is SourceRunStatus.SUCCESS


def test_partial_http_snapshot_never_closes_absent_jobs(
    tmp_path,
    monkeypatch,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="liepin_http",
                source_name="猎聘",
                query="AI应用工程师",
            ),
        ),
    )
    source = configured.sources[0].source
    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._CDPSession.minimize_windows",
        lambda: None,
    )
    monkeypatch.setattr(
        core.discovery,
        "discover",
        lambda **_: (ImportSummary(40, 40, 0, (), snapshot_complete=False),),
    )

    def fail_if_closed(**_: object) -> None:
        raise AssertionError("partial HTTP snapshots cannot close absent jobs")

    monkeypatch.setattr(core.jobs, "mark_missing_closed", fail_if_closed)

    result = core.search._discover_sources(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        sources=(source,),
    )

    assert result[0].status is SourceRunStatus.SUCCESS


def test_complete_snapshot_can_close_absent_jobs(tmp_path, monkeypatch) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="json_file",
                source_name="完整岗位快照",
                path=str(tmp_path / "jobs.json"),
            ),
        ),
    )
    source = configured.sources[0].source
    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._CDPSession.minimize_windows",
        lambda: None,
    )
    monkeypatch.setattr(
        core.discovery,
        "discover",
        lambda **_: (ImportSummary(0, 0, 0, (), snapshot_complete=True),),
    )
    calls: list[dict] = []
    monkeypatch.setattr(
        core.jobs, "mark_missing_closed", lambda **values: calls.append(values)
    )

    result = core.search._discover_sources(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        sources=(source,),
    )

    assert result[0].status is SourceRunStatus.SUCCESS
    assert len(calls) == 1
    assert calls[0]["observed_job_ids"] == set()


def test_search_skips_retired_source_but_keeps_workspace_usable(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="lagou_cdp",
                source_name="拉勾",
                query="AI应用工程师",
            ),
        ),
    )

    result = core.search_jobs_with_diagnostics(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        allow_browser_sources=True,
    )

    assert result.matches == ()
    assert result.diagnostics.source_runs[0].status is SourceRunStatus.SKIPPED
    assert "停用" in (result.diagnostics.source_runs[0].error or "")


def test_fast_search_refreshes_boss_for_each_city_and_uses_other_caches(
    tmp_path,
    monkeypatch,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海", "杭州"],
    )
    discovered = []

    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._CDPSession.minimize_windows",
        lambda: None,
    )

    def discover(**kwargs):
        source = kwargs["sources"][0]
        discovered.append(source.source_name)
        return (ImportSummary(0, 0, 0, ()),)

    monkeypatch.setattr(core.discovery, "discover", discover)

    result = core.search_jobs_with_diagnostics(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        allow_browser_sources=True,
        refresh_mode=SearchRefreshMode.FAST,
    )

    assert set(discovered) == {
        "BOSS直聘·上海",
        "BOSS直聘·杭州",
        "猎聘·上海",
        "猎聘·杭州",
        "智联招聘·上海",
        "智联招聘·杭州",
        "前程无忧·上海",
        "前程无忧·杭州",
    }
    assert result.diagnostics.refresh_mode is SearchRefreshMode.FAST
    assert (
        sum(
            run.status is SourceRunStatus.SKIPPED
            for run in result.diagnostics.source_runs
        )
        == 0
    )


def test_cache_search_performs_no_remote_discovery(tmp_path, monkeypatch) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        locations=["上海"],
    )

    def fail_discovery(**_: object) -> None:
        raise AssertionError("cache mode cannot perform remote discovery")

    monkeypatch.setattr(core.discovery, "discover", fail_discovery)

    result = core.search_jobs_with_diagnostics(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        allow_browser_sources=True,
        refresh_mode=SearchRefreshMode.CACHE,
    )

    assert result.diagnostics.refresh_mode is SearchRefreshMode.CACHE
    assert all(
        run.status is SourceRunStatus.SKIPPED for run in result.diagnostics.source_runs
    )


def test_empty_browser_refresh_uses_existing_cache_as_degraded(
    tmp_path,
    monkeypatch,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    configured = core.configure_search(
        target_roles=["AI应用工程师"],
        sources=(
            DiscoverySource(
                kind="boss_cdp",
                source_name="BOSS直聘",
                query="AI应用工程师",
            ),
        ),
    )
    source = configured.sources[0].source
    core.job_imports.import_records(
        configured.workspace.workspace_id,
        parse_json(
            """
            [{
              "id": "cached",
              "title": "AI应用工程师",
              "company": "示例科技",
              "description": "Python RAG Agent",
              "url": "https://example.com/jobs/cached"
            }]
            """,
            source_name=source.source_name,
        ),
    )
    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._CDPSession.minimize_windows",
        lambda: None,
    )
    monkeypatch.setattr(
        core.discovery,
        "discover",
        lambda **_: (ImportSummary(0, 0, 0, ()),),
    )

    run = core.search._discover_sources(
        workspace_id=configured.workspace.workspace_id,
        plan_id=configured.plan.plan_id,
        sources=(source,),
    )[0]

    assert run.status is SourceRunStatus.DEGRADED
    assert run.cache_used is True
    assert "using cached records" in (run.error or "")


def _setup_profile(core, resume_path):
    """Import a resume and auto-confirm all facts."""
    imported = core.import_resume(source_path=str(resume_path))
    return core.confirm_profile(
        profile_id=imported.profile_id,
        accepted_fact_ids=[f.fact_id for f in imported.facts],
    )


def test_suggest_plan_returns_ready_false_without_confirmed_profile(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    suggestion = core.suggest_plan()
    assert suggestion.ready is False
    assert suggestion.reasoning  # should explain what's missing


def test_suggest_plan_derives_roles_from_ai_skills(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：Python、RAG、LangChain、Agent\n"
        "项目经历：\n"
        "2023.06-2025.03 某AI公司 大模型应用工程师\n"
        "负责基于LangGraph的Agent系统开发，使用RAG技术构建知识库问答系统。\n"
        "教育经历：\n"
        "2019-2023 上海大学 计算机科学 本科\n",
        encoding="utf-8",
    )
    _setup_profile(core, resume)
    suggestion = core.suggest_plan()
    assert suggestion.ready is True
    assert "AI应用工程师" in suggestion.target_roles
    assert "上海" in suggestion.locations  # detected from education text
    assert suggestion.recruitment_track is None
    assert suggestion.employment_type is None


def test_suggest_plan_derives_locations_from_experience(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：Python、Docker、PostgreSQL\n"
        "工作经历：\n"
        "2022.07-至今 深圳腾讯 后端开发工程师\n"
        "2020.03-2022.06 杭州阿里巴巴 Java开发\n"
        "教育经历：\n"
        "2016-2020 浙江大学 计算机科学\n",
        encoding="utf-8",
    )
    _setup_profile(core, resume)
    suggestion = core.suggest_plan()
    assert suggestion.ready is True
    assert "深圳" in suggestion.locations or "杭州" in suggestion.locations
    # Backend signals should suggest backend role
    assert any(r in str(suggestion.target_roles) for r in ("后端", "AI应用"))


def test_suggest_plan_estimates_experience_and_salary(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：PyTorch、TensorFlow、Python\n"
        "工作经历：\n"
        "2020.07-至今 北京字节跳动 算法工程师 6年\n"
        "2018.03-2020.06 上海商汤科技 机器学习研究员\n"
        "教育经历：\n"
        "2015-2018 清华大学 计算机科学 硕士\n",
        encoding="utf-8",
    )
    _setup_profile(core, resume)
    suggestion = core.suggest_plan()
    assert suggestion.ready is True
    # Experience is evidence; desired salary is not inferred from years alone.
    assert suggestion.salary_min_k is None
    assert "salary_min_k" in suggestion.requires_confirmation
    assert suggestion.experience_max_years is not None
    assert suggestion.experience_max_years >= 6
    assert suggestion.candidate_experience_years == suggestion.experience_max_years
    # Strong ML signals should suggest 算法工程师
    assert "算法工程师" in suggestion.target_roles


def test_suggest_plan_does_not_force_social_full_time_without_evidence(
    tmp_path,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    resume = tmp_path / "resume.txt"
    resume.write_text("技能：Python、RAG、Agent", encoding="utf-8")
    _setup_profile(core, resume)

    suggestion = core.suggest_plan()

    assert suggestion.recruitment_track is None
    assert suggestion.employment_type is None
    assert "recruitment_track" in suggestion.requires_confirmation


def test_suggest_plan_does_not_double_count_explicit_years_and_date_ranges(
    tmp_path,
) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    resume = tmp_path / "resume.txt"
    resume.write_text(
        "技能：Python、RAG、Agent\n"
        "工作经历：\n"
        "2020.07-2026.06 示例科技 AI应用工程师 6年\n",
        encoding="utf-8",
    )
    _setup_profile(core, resume)

    suggestion = core.suggest_plan()

    assert suggestion.candidate_experience_years == 6
