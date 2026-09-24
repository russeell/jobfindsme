from __future__ import annotations

from jobfindsme.branding import (
    DB_ENV,
    LEGACY_DB_ENV,
    data_root,
    database_path,
    runtime_python,
)


def test_new_install_uses_agent_job_search_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(DB_ENV, raising=False)
    monkeypatch.delenv(LEGACY_DB_ENV, raising=False)
    assert data_root(tmp_path) == tmp_path / ".agent-job-search"
    assert database_path(tmp_path) == (
        tmp_path / ".agent-job-search" / "data" / "agent-job-search.db"
    )
    assert runtime_python(tmp_path) == (
        tmp_path / ".agent-job-search" / "runtime" / "bin" / "python"
    )


def test_legacy_install_is_reused_until_new_root_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(DB_ENV, raising=False)
    monkeypatch.delenv(LEGACY_DB_ENV, raising=False)
    legacy_runtime = tmp_path / ".jobfindsme" / "runtime" / "bin" / "python"
    legacy_runtime.parent.mkdir(parents=True)
    legacy_runtime.touch()
    legacy_database = tmp_path / ".jobfindsme" / "data" / "jobfindsme.db"
    legacy_database.parent.mkdir(parents=True)
    legacy_database.touch()

    assert data_root(tmp_path) == tmp_path / ".jobfindsme"
    assert database_path(tmp_path) == legacy_database
    assert runtime_python(tmp_path) == legacy_runtime

    # Merely creating the new runtime root must not hide existing user data.
    (tmp_path / ".agent-job-search" / "runtime").mkdir(parents=True)
    assert data_root(tmp_path) == tmp_path / ".jobfindsme"

    current_database = tmp_path / ".agent-job-search" / "data" / "agent-job-search.db"
    current_database.parent.mkdir(parents=True)
    current_database.touch()
    assert data_root(tmp_path) == tmp_path / ".agent-job-search"


def test_new_database_environment_variable_wins(monkeypatch, tmp_path) -> None:
    current = tmp_path / "current.db"
    legacy = tmp_path / "legacy.db"
    monkeypatch.setenv(LEGACY_DB_ENV, str(legacy))
    monkeypatch.setenv(DB_ENV, str(current))

    assert database_path(tmp_path) == current
