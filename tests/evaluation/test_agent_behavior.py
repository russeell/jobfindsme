from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jobfindsme.evaluation.agent_behavior.evaluator import evaluate_behavior_suite

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals/agent_behavior/cases.json"
BASELINE = ROOT / "evals/agent_behavior/fixtures/baseline.json"
WITH_SKILL = ROOT / "evals/agent_behavior/fixtures/with_skill.json"


def test_acceptance_prompts_cover_the_six_user_critical_behaviors() -> None:
    suite = json.loads(CASES.read_text(encoding="utf-8"))

    assert {case["case_id"] for case in suite["cases"]} == {
        "find_jobs_with_resume",
        "preserve_five_sections_and_links",
        "explain_source_degradation",
        "mark_job_applied",
        "incremental_search",
        "protect_resume_context",
    }
    assert all(case["prompt"].strip() for case in suite["cases"])


def test_baseline_demonstrates_failure_before_the_skill() -> None:
    report = evaluate_behavior_suite(CASES, BASELINE)

    assert report.skill_enabled is False
    assert report.gate_passed is False
    assert set(report.failed_case_ids) == {
        "find_jobs_with_resume",
        "preserve_five_sections_and_links",
        "explain_source_degradation",
        "mark_job_applied",
        "incremental_search",
        "protect_resume_context",
    }


def test_skill_fixture_passes_every_behavior_gate() -> None:
    report = evaluate_behavior_suite(CASES, WITH_SKILL)

    assert report.skill_enabled is True
    assert report.gate_passed is True
    assert report.failed_case_ids == ()
    assert report.passed == report.total == 6


def test_contract_fixture_cannot_be_claimed_as_live_agent_evidence(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "jobfindsme.evaluation.agent_behavior.cli",
            "--cases",
            str(CASES),
            "--transcripts",
            str(WITH_SKILL),
            "--report",
            str(tmp_path / "report.json"),
            "--expect",
            "pass",
            "--require-evidence",
            "live_agent",
            "--require-host",
            "codex",
            "--require-host",
            "claude",
            "--require-host",
            "cursor",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "Required evidence 'live_agent'" in completed.stdout
