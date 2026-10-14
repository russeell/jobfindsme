"""Freeze a verified release environment and record the actual Python inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def source_digest(root: Path) -> str:
    spec = json.loads((root / "scripts/desktop-build-inputs.json").read_text())[
        "python"
    ]
    paths = {root / file for file in spec["files"]}
    for directory in spec["directories"]:
        paths.update(
            path
            for path in (root / directory).rglob("*")
            if path.is_file() and path.suffix in spec["extensions"]
        )
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def verify_dependencies(lock: Path) -> None:
    for line in lock.read_text().splitlines():
        if not line or line[0] in " #\\":
            continue
        requirement = Requirement(line.removesuffix(" \\"))
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed = version(requirement.name)
        except PackageNotFoundError as error:
            raise RuntimeError(
                f"Release dependency missing: {requirement.name}"
            ) from error
        if installed not in requirement.specifier:
            raise RuntimeError(
                f"Release dependency mismatch: {requirement.name} "
                f"{installed} != {requirement.specifier}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distpath", default="apps/desktop/runtime/python")
    parser.add_argument("--workpath", default="build/jobfindsme-api")
    args = parser.parse_args()
    lock = ROOT / "requirements/release.txt"
    verify_dependencies(lock)
    digest = source_digest(ROOT)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--distpath",
            args.distpath,
            "--workpath",
            args.workpath,
            "scripts/jobfindsme_api.spec",
        ],
        cwd=ROOT,
        check=True,
    )
    if source_digest(ROOT) != digest:
        raise RuntimeError("Python inputs changed during freezing; rebuild")
    metadata = {
        "sourceCommit": commit,
        "sourceDigest": digest,
        "dependencyLock": hashlib.sha256(lock.read_bytes()).hexdigest(),
    }
    directory = Path(args.distpath)
    if not directory.is_absolute():
        directory = ROOT / directory
    (directory / "jobfindsme-api/build-provenance.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
