from jobfindsme.profiles.models import FactType
from jobfindsme.profiles.parser import DeterministicResumeParser


def test_parser_returns_deduplicated_facts_with_exact_evidence() -> None:
    text = """# Skills
Python, FastAPI, Python, RAG

# Projects
- jobfindsme uses MCP for local job search
"""

    facts = DeterministicResumeParser().parse(text)

    assert [fact.value for fact in facts].count("Python") == 1
    assert any(fact.fact_type is FactType.PROJECT for fact in facts)
    for fact in facts:
        assert text[fact.evidence_start : fact.evidence_end] == (fact.evidence_snippet)


def test_parser_v3_groups_wrapped_resume_sections_without_line_noise() -> None:
    text = """独立实践与工作经历
2025.01-2025.06 jobfindsme
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


def test_inline_section_labels_yield_reviewable_facts_without_private_basics():
    from jobfindsme.profiles.models import FactType

    text = (
        "姓名：测试用户\n求职意向：AI 应用工程师\n"
        "教育经历：示例大学 计算机科学 本科\n"
        "工作经历：示例公司 2022-2025 开发企业知识库应用\n"
        "项目经历：使用 Python 和检索增强技术实现问答系统，负责接口与评估。\n"
        "技能：Python、TypeScript、SQL、RAG\n"
    )
    facts = DeterministicResumeParser().parse(text)
    kinds = {item.fact_type for item in facts}
    assert {FactType.EDUCATION, FactType.EXPERIENCE, FactType.PROJECT} <= kinds
    assert all("测试用户" not in item.value for item in facts)
    assert all(
        "技能：" not in item.value
        for item in facts
        if item.fact_type is FactType.PROJECT
    )
