from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evaluation.metrics.golden_runner import evaluate_golden_dataset
from evaluation.metrics.runner import (
    evaluate_chinese_dataset,
    evaluate_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--type",
        choices=("synthetic", "chinese", "golden"),
        default="synthetic",
        help="Dataset type (default: synthetic)",
    )
    parser.add_argument(
        "--require-claim-ready",
        action="store_true",
        help="Fail unless a Chinese dataset has verified field provenance.",
    )
    args = parser.parse_args()

    if args.type == "chinese":
        try:
            report = evaluate_chinese_dataset(args.dataset)
        except FileNotFoundError:
            print(
                f"Chinese benchmark dataset not found: {args.dataset}", file=sys.stderr
            )
            return 2
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            report.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        print(report.summary())
        return int(args.require_claim_ready and not report.ready_for_claim)

    if args.type == "golden":
        report = evaluate_golden_dataset(args.dataset)
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            report.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        print(report.summary())
        return 0 if report.gate_passed else 1

    report = evaluate_dataset(args.dataset)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(report_path)
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
