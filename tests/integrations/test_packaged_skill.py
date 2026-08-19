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
    source = (root / "skills" / "jobfindsme" / "SKILL.md").read_text()

    assert packaged == source


def test_skill_contract_keeps_apply_links_as_bare_urls() -> None:
    """The output contract must keep links as bare URLs on their own line.

    Regression guard: Markdown-wrapped links (🔗 [投递链接](url)) break
    clickability on terminal clients that auto-link bare URLs instead of
    rendering Markdown. Any future change must not reintroduce wrapping.
    """
    root = Path(__file__).parents[2]
    skill = (root / "skills" / "jobfindsme" / "SKILL.md").read_text()

    assert "bare URL" in skill
    assert "投递链接：https://" in skill  # the canonical bare-URL form
    # No positive instruction to wrap links in Markdown
    assert "[投递链接](" not in skill
    assert "as a clickable Markdown link" not in skill


def test_skill_grounds_answer_in_facts_and_keeps_incremental_semantics() -> None:
    root = Path(__file__).parents[2]
    skill = (root / "skills" / "jobfindsme" / "SKILL.md").read_text()

    assert "five-section baseline" in skill
    assert "structuredContent.jobs" in skill
    assert "never invent jobs" in skill
    assert "never rebuild results as a table" in skill
    assert "previously shown unchanged" in skill
    assert "jobs, not duplicates" in skill
    assert "Never automatically retry it with" in skill
    assert "Never invent CLI search syntax" in skill
    assert "Never search, list, or scan the user's directories" in skill
