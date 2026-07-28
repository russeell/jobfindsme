from jobfindsme.profiles.models import FactType
from jobfindsme.profiles.parser import DeterministicResumeParser


def test_parser_returns_deduplicated_facts_with_exact_evidence() -> None:
    text = """# Skills
Python, FastAPI, Python, RAG

# Projects
- JobFindsMe uses MCP for local job search
"""

    facts = DeterministicResumeParser().parse(text)

    assert [fact.value for fact in facts].count("Python") == 1
    assert any(fact.fact_type is FactType.PROJECT for fact in facts)
    for fact in facts:
        assert text[fact.evidence_start : fact.evidence_end] == (fact.evidence_snippet)


def test_parser_v3_groups_wrapped_resume_sections_without_line_noise() -> None:
    text = """独立实践与工作经历
2025.01-2025.06 JobFindsMe
负责 Agent 与 MCP 工具设计，
并使用 Pydantic、pytest 和 RRF 完成质量门禁。
教育背景
2020.09-2024.06 示例大学
计算机科学与技术 本科
"""

    facts = DeterministicResumeParser().parse(text)

    experience = [fact for fact in facts if fact.fact_type is FactType.EXPERIENCE]
    education = [fact for fact in facts if fact.fact_type is FactType.EDUCATION]
    skills = {fact.value for fact in facts if fact.fact_type is FactType.SKILL}
    assert len(experience) == 1
    assert "负责 Agent 与 MCP 工具设计" in experience[0].value
    assert len(education) == 1
    assert {"Pydantic", "pytest", "RRF"} <= skills
    assert all(
        text[fact.evidence_start : fact.evidence_end] == fact.evidence_snippet
        for fact in facts
    )
