from __future__ import annotations

from pathlib import Path

from evaluation.regression.radar_replay import run_radar_replay

FIXTURES = Path(__file__).parents[2] / "evaluation" / "data" / "radar_replay"


def _run():
    return run_radar_replay(
        [FIXTURES / "day1.json", FIXTURES / "day2.json", FIXTURES / "day3.json"],
        apply_after_days=[(2, "D")],
    )


def test_radar_replay_compresses_a_week_into_three_days() -> None:
    report, _ = _run()

    assert len(report.days) == 3
    day1, day2, day3 = report.days

    # Day 1: everything is new.
    assert day1.new == 3
    assert day1.changed == day1.closed == day1.repeated_suppressed == 0
    assert set(day1.change_types.values()) == {"new"}

    # Day 2: only the newcomer is shown; seen jobs are suppressed.
    assert day2.new == 1
    assert day2.repeated_suppressed == 3
    assert day2.changed == day2.closed == 0

    # Day 3: A changed, B closed, E new; C-dup deduped; applied D suppressed.
    assert day3.new == 1
    assert day3.changed == 1
    assert day3.closed == 1
    assert set(day3.change_types.values()) == {"new", "changed"}


def test_applied_job_is_never_re_suggested_even_when_changed() -> None:
    report, core = _run()
    day2, day3 = report.days[1], report.days[2]
    workspace_id = core.context.resolve_workspace().workspace_id

    applied_id = next(
        job.job_id for job in core.jobs.list(workspace_id) if job.external_id == "D"
    )
    assert applied_id in day2.shown_ids
    assert applied_id not in day3.shown_ids
    assert applied_id in report.applied_job_ids


def test_duplicate_posting_does_not_inflate_new_count() -> None:
    report, _ = _run()
    # Day 3 contains a duplicate posting of C; only E may be new.
    assert report.days[2].new == 1
