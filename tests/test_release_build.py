import importlib.util
from pathlib import Path

import pytest


def test_freeze_refuses_wrong_or_missing_release_dependencies(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "freeze_desktop_api",
        Path(__file__).parents[1] / "scripts/freeze_desktop_api.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock = tmp_path / "release.txt"
    lock.write_text("example==1.2.3 \\\n    --hash=sha256:fixture\n")
    monkeypatch.setattr(module, "version", lambda name: "1.2.3")
    module.verify_dependencies(lock)
    monkeypatch.setattr(module, "version", lambda name: "1.2.4")
    with pytest.raises(RuntimeError, match="dependency mismatch"):
        module.verify_dependencies(lock)

    def missing(name):
        raise module.PackageNotFoundError(name)

    monkeypatch.setattr(module, "version", missing)
    with pytest.raises(RuntimeError, match="dependency missing"):
        module.verify_dependencies(lock)
