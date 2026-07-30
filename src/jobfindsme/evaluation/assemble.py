"""CLI for assembling claim-verifiable Chinese field-trial evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from jobfindsme.evaluation.labeling import (
    assemble_field_trial_dataset,
    write_labeled_dataset,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble human labels and Live Loop reports into field evidence."
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--labeler", required=True)
    parser.add_argument("--days", nargs="+", type=Path, required=True)
    parser.add_argument("--loop-reports", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotation-guide-version", default="0.2")
    args = parser.parse_args(argv)

    dataset = assemble_field_trial_dataset(
        version=args.version,
        labeler=args.labeler,
        day_paths=args.days,
        report_paths=args.loop_reports,
        annotation_guide_version=args.annotation_guide_version,
    )
    write_labeled_dataset(args.output, dataset)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
