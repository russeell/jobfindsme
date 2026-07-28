import json

import pytest

from scripts.feature_harness import (
    CheckResult,
    HarnessError,
    check_allowed_paths,
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
