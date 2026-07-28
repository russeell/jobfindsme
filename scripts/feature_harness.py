from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = ROOT / "specs" / "feature_list.json"


class HarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckResult:
    command: list[str]
    returncode: int
    output: str


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
