from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_real_world_smoke_cli_tracks_the_current_product_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root))),
    }

    completed = subprocess.run(
        [sys.executable, "scripts/real_world_smoke.py", "--help"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "--role ROLE" in completed.stdout
    assert "{live,cache}" in completed.stdout
    assert "--no-allow-browser-sources" in completed.stdout
    assert "--asset" not in completed.stdout


def test_real_world_smoke_cache_mode_runs_end_to_end(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    reports = tmp_path / "evidence"
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root))),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/real_world_smoke.py",
            "--db",
            str(tmp_path / "jobfindsme.db"),
            "--reports-dir",
            str(reports),
            "--refresh-mode",
            "cache",
            "--no-allow-browser-sources",
            "--no-use-profile",
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    output = json.loads(completed.stdout)
    report = json.loads((reports / "latest_four_source_search.json").read_text())
    assert output["ok"] is True
    assert report["smoke"]["configure_ok"] is True
    assert report["smoke"]["search_ok"] is True
    assert report["smoke"]["layers_present"] is True
