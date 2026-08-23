from __future__ import annotations

import pytest

from jobfindsme.taxonomy import (
    SKILL_ALIASES,
    SKILL_TAXONOMY_VERSION,
    extract_skills,
    is_target_role_candidate,
    validate_skill_taxonomy,
)


def test_packaged_taxonomy_is_versioned_and_covers_current_agent_stack() -> None:
    assert SKILL_TAXONOMY_VERSION
    expected = {"Dify", "AutoGen", "CrewAI", "smolagents", "mem0", "Qdrant", "Weaviate"}
    assert expected <= set(SKILL_ALIASES)


def test_new_taxonomy_terms_are_extractable() -> None:
    found = extract_skills("使用 Dify、Qdrant 和 CrewAI 构建 Agent")
    assert set(found) >= {"Dify", "Qdrant", "CrewAI", "Agent"}


def test_taxonomy_rejects_cross_skill_alias_collisions() -> None:
    with pytest.raises(ValueError, match="belongs to both"):
        validate_skill_taxonomy(
            {
                "version": "test",
                "skills": {"First": ["shared"], "Second": ["SHARED"]},
            }
        )


@pytest.mark.parametrize(
    "title",
    ["AI售前工程师", "AI销售经理", "人工智能产品运营", "AI客户成功经理"],
)
def test_ai_signal_does_not_override_non_engineering_role(title: str) -> None:
    assert not is_target_role_candidate(title, "RAG Agent", ("AI应用工程师",))
