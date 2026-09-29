import pytest

from jobfindsme.research.agent_store import _claim_basis


@pytest.mark.parametrize(
    ("statement", "quote"),
    [
        ("示例公司利润100亿元，营收10亿元", "示例公司营收100亿元，利润10亿元"),
        (
            "示例公司北京团队加班10小时，上海团队加班20小时",
            "示例公司北京团队加班20小时，上海团队加班10小时",
        ),
    ],
)
def test_sensitive_claim_relationship_swap_is_rejected(statement, quote):
    with pytest.raises(ValueError):
        _claim_basis(
            {
                "statement": statement,
                "quote": quote,
                "category": "business",
                "evidence_ids": ["e"],
            },
            {"excerpt": quote},
            "示例公司",
        )


def test_current_verbatim_source_statement_can_be_saved():
    quote = "示例公司目前在上海设立了研发团队"
    assert (
        _claim_basis(
            {
                "statement": quote,
                "quote": quote,
                "category": "business",
                "evidence_ids": ["e"],
            },
            {"excerpt": quote},
            "示例公司",
        )["statement"]
        == quote
    )
