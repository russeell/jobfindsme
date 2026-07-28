from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def test_packaged_and_source_skills_are_identical() -> None:
    packaged = (
        files("jobfindsme.resources.jobfindsme")
        .joinpath("SKILL.md")
        .read_text(encoding="utf-8")
    )
    root = Path(__file__).parents[2]
    source = (root / "integrations" / "shared" / "SKILL.md").read_text()

    assert packaged == source
