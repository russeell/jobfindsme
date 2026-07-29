from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = ROOT / "specs" / "feature_list.json"


class HarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckResult:
    command: list[str]
    returncode: int
    output: str


REQUIRED_RESEARCH_CATEGORIES = {
    "open_source",
    "official_guide",
    "paper_or_benchmark",
}


def load_spec(path: Path = FEATURES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_feature(spec: dict[str, Any], feature_id: str) -> dict[str, Any]:
    for feature in spec["features"]:
        if feature["id"] == feature_id:
            return feature
    raise HarnessError(f"unknown feature: {feature_id}")


def next_feature(spec: dict[str, Any]) -> dict[str, Any] | None:
    statuses = {feature["id"]: feature["status"] for feature in spec["features"]}
    candidates = []
    for feature in spec["features"]:
        if feature["status"] not in {"in_progress", "ready"}:
            continue
        if all(statuses.get(item) == "done" for item in feature["blocked_by"]):
            candidates.append(feature)
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item["status"] != "in_progress",
            spec["features"].index(item),
        )
    )
    return candidates[0]


def normalize_command(value: list[str] | str) -> list[str]:
    if isinstance(value, str):
        return shlex.split(value)
    return value


def path_is_allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def changed_paths(root: Path = ROOT) -> list[str]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return sorted(set(tracked + untracked))


def check_allowed_paths(feature: dict[str, Any], paths: list[str]) -> None:
    rejected = [
        path for path in paths if not path_is_allowed(path, feature["allowed_paths"])
    ]
    if rejected:
        joined = ", ".join(rejected)
        raise HarnessError(f"paths outside {feature['id']} scope: {joined}")


def check_research_gate(
    feature: dict[str, Any],
    *,
    required_categories: set[str] = REQUIRED_RESEARCH_CATEGORIES,
) -> None:
    """Require reviewable external evidence before high-risk design work."""

    if not feature.get("design_research_required", False):
        return

    references = feature.get("research_refs", [])
    categories = {
        reference.get("category")
        for reference in references
        if isinstance(reference, dict)
    }
    missing_categories = required_categories - categories
    if missing_categories:
        missing = ", ".join(sorted(missing_categories))
        raise HarnessError(
            f"{feature['id']} research gate missing categories: {missing}"
        )

    required_fields = {
        "category",
        "title",
        "url",
        "adopted_pattern",
        "rejected_or_not_adopted",
    }
    for index, reference in enumerate(references, start=1):
        if not isinstance(reference, dict):
            raise HarnessError(
                f"{feature['id']} research reference {index} must be an object"
            )
        missing_fields = [
            field for field in required_fields if not reference.get(field)
        ]
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise HarnessError(
                f"{feature['id']} research reference {index} missing: {missing}"
            )
        parsed = urlparse(str(reference["url"]))
        if parsed.scheme != "https" or not parsed.netloc:
            raise HarnessError(
                f"{feature['id']} research reference {index} must use https"
            )

    constraints = feature.get("local_constraints", [])
    if not isinstance(constraints, list) or not constraints:
        raise HarnessError(f"{feature['id']} research gate needs local_constraints")
    if any(not isinstance(item, str) or not item.strip() for item in constraints):
        raise HarnessError(
            f"{feature['id']} local_constraints must be non-empty strings"
        )


def research_gate_required(spec: dict[str, Any], feature: dict[str, Any]) -> bool:
    """Return whether a feature falls within the project research policy."""

    policy = spec.get("research_policy")
    if not isinstance(policy, dict):
        return False
    enforced_from = policy.get("enforced_from_feature")
    if not enforced_from:
        return False
    feature_ids = [item["id"] for item in spec["features"]]
    try:
        return feature_ids.index(feature["id"]) >= feature_ids.index(enforced_from)
    except ValueError as error:
        raise HarnessError("research policy references an unknown feature") from error


def check_project_research_gate(spec: dict[str, Any], feature: dict[str, Any]) -> None:
    required = research_gate_required(spec, feature)
    if required and not feature.get("design_research_required", False):
        raise HarnessError(
            f"{feature['id']} must declare design_research_required "
            "under project policy"
        )
    policy = spec.get("research_policy", {})
    categories = set(policy.get("required_categories", REQUIRED_RESEARCH_CATEGORIES))
    check_research_gate(feature, required_categories=categories)


def run_checks(feature: dict[str, Any], root: Path = ROOT) -> list[CheckResult]:
    results = []
    for raw_command in feature.get("checks", []):
        command = normalize_command(raw_command)
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
        )
        results.append(
            CheckResult(
                command=command,
                returncode=completed.returncode,
                output=completed.stdout + completed.stderr,
            )
        )
    return results


def write_evidence(
    feature: dict[str, Any],
    *,
    paths: list[str],
    results: list[CheckResult],
    root: Path = ROOT,
) -> Path:
    evidence_path = feature.get(
        "evidence_path", f"reports/features/{feature['id']}.json"
    )
    destination = root / evidence_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    passed = bool(results) and all(item.returncode == 0 for item in results)
    payload = {
        "feature_id": feature["id"],
        "status": "passed" if passed else "failed",
        "verified_at": datetime.now(UTC).isoformat(),
        "changed_paths": paths,
        "checks": [
            {
                "command": item.command,
                "returncode": item.returncode,
                "output": item.output[-4000:],
            }
            for item in results
        ],
    }
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def evidence_passed(feature: dict[str, Any], root: Path = ROOT) -> bool:
    evidence_path = feature.get(
        "evidence_path", f"reports/features/{feature['id']}.json"
    )
    path = root / evidence_path
    if not path.exists():
        return False
    evidence = json.loads(path.read_text(encoding="utf-8"))
    return (
        evidence.get("feature_id") == feature["id"]
        and evidence.get("status") == "passed"
    )
