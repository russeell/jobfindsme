from __future__ import annotations

from jobfindsme.contracts import JobChangeType, JobLiveness, JobStateKind
from jobfindsme.core import jobfindsmecore
from jobfindsme.importing.parsers import parse_json


def _core_with_job(tmp_path):
    path = tmp_path / "jobfindsme.db"
    core = jobfindsmecore(path)
    workspace = core.create_workspace("Radar")
    plan = core.create_search_plan(
        workspace_id=workspace.workspace_id,
        name="AI",
        target_roles=["AI应用工程师"],
    )
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            """
            [{
              "id": "ai-1",
              "title": "AI应用工程师",
              "company": "示例科技",
              "description": "Python RAG Agent",
              "url": "https://example.com/jobs/ai-1"
            }]
            """,
            source_name="fixture",
        ),
    )
    return path, core, workspace, plan


def test_first_search_records_new_then_repeat_is_suppressed(tmp_path) -> None:
    _, core, workspace, plan = _core_with_job(tmp_path)

    first = core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )
    second = core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )

    assert first.matches[0].change_type is JobChangeType.NEW
    assert first.matches[0].first_seen_at is not None
    assert first.changes.new == 1
    assert second.matches == ()
    assert second.changes.repeated_suppressed == 1
    assert second.diagnostics.repeated_suppressed_count == 1


def test_seen_baseline_is_reused_by_another_agent_process(tmp_path) -> None:
    path, first_core, workspace, plan = _core_with_job(tmp_path)
    first_core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )

    second_core = jobfindsmecore(path)
    result = second_core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )

    assert result.matches == ()
    assert result.changes.repeated_suppressed == 1


def test_explicit_history_returns_unchanged_job_and_persisted_state(tmp_path) -> None:
    _, core, workspace, plan = _core_with_job(tmp_path)
    first = core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )
    core.update_job_state(
        workspace_id=workspace.workspace_id,
        job_id=first[0].job.job_id,
        state=JobStateKind.SAVED,
    )

    history = core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
        include_seen=True,
    )

    assert history[0].change_type is JobChangeType.UNCHANGED
    assert history[0].state is JobStateKind.SAVED


def test_material_job_version_change_is_returned_again(tmp_path) -> None:
    _, core, workspace, plan = _core_with_job(tmp_path)
    core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            """
            [{
              "id": "ai-1",
              "title": "AI应用工程师",
              "company": "示例科技",
              "description": "Python RAG Agent MCP，新增向量检索要求",
              "url": "https://example.com/jobs/ai-1"
            }]
            """,
            source_name="fixture",
        ),
    )

    changed = core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )

    assert changed.matches[0].change_type is JobChangeType.CHANGED
    assert changed.changes.changed == 1


def test_closed_then_reopened_job_is_reported_once_per_transition(tmp_path) -> None:
    _, core, workspace, plan = _core_with_job(tmp_path)
    first = core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )[0]
    closed_job = first.job.model_copy(
        update={
            "source": first.job.source.model_copy(
                update={"liveness": JobLiveness.CLOSED}
            )
        }
    )
    core.jobs.upsert(workspace.workspace_id, closed_job)

    closed = core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )
    assert closed.matches == ()
    assert closed.changes.closed == 1
    assert closed.changes.closed_job_ids == (first.job.job_id,)

    core.jobs.upsert(workspace.workspace_id, first.job)
    reopened = core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )

    assert reopened.matches[0].change_type is JobChangeType.REOPENED
    assert reopened.changes.reopened == 1


def test_applied_job_is_never_re_suggested_in_daily_push(tmp_path) -> None:
    """Daily-push scenario: jobs marked applied must not be re-suggested,
    even when they were applied before ever being shown by search."""
    _, core, workspace, plan = _core_with_job(tmp_path)
    first = core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )[0]
    core.update_job_state(
        workspace_id=workspace.workspace_id,
        job_id=first.job.job_id,
        state=JobStateKind.APPLIED,
    )

    # Simulate a fresh process/day: impressions for this job exist but the
    # APPLIED state must suppress it from the daily push regardless.
    daily = core.search_jobs_with_diagnostics(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
    )

    assert daily.matches == ()
    assert daily.changes.repeated_suppressed == 1
    # History view still shows the applied job for review
    history = core.search_jobs(
        workspace_id=workspace.workspace_id,
        plan_id=plan.plan_id,
        refresh_mode="cache",
        include_seen=True,
    )
    assert history[0].state is JobStateKind.APPLIED
    assert history[0].change_type is JobChangeType.UNCHANGED
