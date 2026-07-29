import json

import pytest

from scripts.feature_harness import (
    CheckResult,
    HarnessError,
    check_allowed_paths,
    check_project_research_gate,
    check_research_gate,
    evidence_passed,
    find_feature,
    next_feature,
    normalize_command,
    write_evidence,
)


def make_spec():
    return {
        "features": [
            {
                "id": "A",
                "status": "done",
                "blocked_by": [],
            },
            {
                "id": "B",
                "status": "ready",
                "blocked_by": ["A"],
            },
            {
                "id": "C",
                "status": "in_progress",
                "blocked_by": ["A"],
            },
        ]
    }


def test_next_feature_prefers_executable_in_progress_work() -> None:
    assert next_feature(make_spec())["id"] == "C"


def test_blocked_dependency_is_not_selected() -> None:
    spec = make_spec()
    spec["features"][0]["status"] = "backlog"
    assert next_feature(spec) is None


def test_unknown_feature_is_rejected() -> None:
    with pytest.raises(HarnessError):
        find_feature(make_spec(), "missing")


def test_allowed_paths_are_enforced() -> None:
    feature = {"id": "A", "allowed_paths": ["src/**", "tests/test_a.py"]}
    check_allowed_paths(feature, ["src/a.py", "tests/test_a.py"])
    with pytest.raises(HarnessError):
        check_allowed_paths(feature, ["README.md"])


def test_commands_accept_arrays_and_legacy_strings() -> None:
    assert normalize_command(["pytest", "tests"]) == ["pytest", "tests"]
    assert normalize_command("pytest tests") == ["pytest", "tests"]


def _researched_feature() -> dict:
    return {
        "id": "DESIGN-001",
        "design_research_required": True,
        "local_constraints": ["No mandatory model API."],
        "research_refs": [
            {
                "category": category,
                "title": category,
                "url": f"https://example.com/{category}",
                "adopted_pattern": "Keep the measurable boundary.",
                "rejected_or_not_adopted": "Do not copy hosted dependencies.",
            }
            for category in (
                "open_source",
                "official_guide",
                "paper_or_benchmark",
            )
        ],
    }


def test_research_gate_accepts_reviewable_evidence() -> None:
    check_research_gate(_researched_feature())


def test_research_gate_requires_all_source_categories() -> None:
    feature = _researched_feature()
    feature["research_refs"] = feature["research_refs"][:2]

    with pytest.raises(HarnessError, match="paper_or_benchmark"):
        check_research_gate(feature)


def test_research_gate_requires_adoption_and_rejection_reasoning() -> None:
    feature = _researched_feature()
    feature["research_refs"][0]["rejected_or_not_adopted"] = ""

    with pytest.raises(HarnessError, match="rejected_or_not_adopted"):
        check_research_gate(feature)


def test_research_gate_requires_local_constraints() -> None:
    feature = _researched_feature()
    feature["local_constraints"] = []

    with pytest.raises(HarnessError, match="local_constraints"):
        check_research_gate(feature)


def test_research_gate_is_opt_in_for_historical_features() -> None:
    check_research_gate({"id": "LEGACY-001"})


def test_project_policy_cannot_be_bypassed_by_omitting_flag() -> None:
    spec = {
        "research_policy": {"enforced_from_feature": "NEW-001"},
        "features": [{"id": "OLD-001"}, {"id": "NEW-001"}],
    }

    check_project_research_gate(spec, spec["features"][0])
    with pytest.raises(HarnessError, match="design_research_required"):
        check_project_research_gate(spec, spec["features"][1])


def test_passing_evidence_is_machine_readable(tmp_path) -> None:
    feature = {
        "id": "A",
        "evidence_path": "reports/features/A.json",
    }
    destination = write_evidence(
        feature,
        paths=["src/a.py"],
        results=[CheckResult(["pytest"], 0, "passed")],
        root=tmp_path,
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert evidence_passed(feature, root=tmp_path)
