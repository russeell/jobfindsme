from __future__ import annotations

import argparse
from pathlib import Path

from jobfindsme.evaluation.agent_behavior.evaluator import evaluate_behavior_suite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate normalized Agent transcripts."
    )
    parser.add_argument("--cases", required=True)
    parser.add_argument("--transcripts", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--expect",
        choices=("pass", "fail"),
        default="pass",
        help="Expected suite gate. Baselines use fail; Skill regressions use pass.",
    )
    parser.add_argument(
        "--require-evidence",
        choices=("contract_fixture", "live_agent"),
        help="Reject reports that do not use the requested evidence class.",
    )
    parser.add_argument(
        "--require-host",
        action="append",
        default=[],
        help="Require a host in the transcript suite; repeat for multiple hosts.",
    )
    args = parser.parse_args()
    report = evaluate_behavior_suite(args.cases, args.transcripts)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        f"Agent behavior: {report.passed}/{report.total} passed "
        f"(skill={report.skill_enabled}, evidence={report.evidence_kind})"
    )
    if args.require_evidence and report.evidence_kind != args.require_evidence:
        print(
            f"Required evidence {args.require_evidence!r}, "
            f"got {report.evidence_kind!r}."
        )
        return 1
    missing_hosts = sorted(set(args.require_host) - set(report.hosts))
    if missing_hosts:
        print(f"Missing required Agent hosts: {', '.join(missing_hosts)}")
        return 1
    expected = report.gate_passed if args.expect == "pass" else not report.gate_passed
    return 0 if expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
