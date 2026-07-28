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
