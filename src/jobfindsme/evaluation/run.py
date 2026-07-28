from __future__ import annotations

import argparse
from pathlib import Path

from jobfindsme.evaluation.runner import evaluate_dataset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

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
