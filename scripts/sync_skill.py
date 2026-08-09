from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills" / "jobfindsme" / "SKILL.md"
PACKAGED = ROOT / "src" / "jobfindsme" / "resources" / "jobfindsme" / "SKILL.md"


def sync(*, check: bool) -> bool:
    canonical = CANONICAL.read_bytes()
    if check:
        return PACKAGED.is_file() and PACKAGED.read_bytes() == canonical
    PACKAGED.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED.write_bytes(canonical)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync the canonical Agent Skill into the Python wheel resources."
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if sync(check=args.check):
        return 0
    print(
        "packaged SKILL.md differs from skills/jobfindsme/SKILL.md; "
        "run python3 scripts/sync_skill.py",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
