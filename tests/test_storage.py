import os
import sqlite3
import stat
from pathlib import Path

import pytest

from jobfindsme.storage import Database, MigrationConflict


def test_secure_sqlite_files_tolerates_disappearing_sidecar(
    tmp_path, monkeypatch
) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.path.touch()
    sidecar = Path(f"{database.path}-shm")
    sidecar.touch()
    real_chmod = os.chmod

    def disappearing_sidecar(path, mode):
        if Path(path) == sidecar:
            sidecar.unlink(missing_ok=True)
            raise FileNotFoundError(path)
        real_chmod(path, mode)

    monkeypatch.setattr(os, "chmod", disappearing_sidecar)

    database._secure_sqlite_files()

    assert stat.S_IMODE(database.path.stat().st_mode) == 0o600


def test_migrations_are_repeatable_and_foreign_keys_are_enabled(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")

    database.migrate()
    database.migrate()

    with database.connect() as connection:
        versions = connection.execute(
            "SELECT version FROM schema_migrations"
        ).fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    applied_versions = [row["version"] for row in versions]
    assert applied_versions == sorted(set(applied_versions))
    assert applied_versions == [
        "0001_workspace",
        "0002_profiles",
        "0003_jobs",
        "0004_user_workflows",
        "0005_monitor_config",
        "0006_monitor_runs",
        "0007_job_state_events",
        "0008_active_context_and_sources",
        "0009_job_source_records",
        "0010_search_plan_filters",
    ]
    assert foreign_keys == 1


def test_reconcile_when_tables_already_exist(tmp_path) -> None:
    """A database with pre-existing tables should reconcile without re-running SQL."""
    database = Database(tmp_path / "jobfindsme.db")

    # Simulate an old DB: create the tables from 0001 by hand,
    # then record a fake old migration name.
    with database.connect() as conn:
        conn.execute(
            """
            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE search_plans (
                plan_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                target_roles_json TEXT NOT NULL,
                locations_json TEXT NOT NULL,
                salary_min_k INTEGER,
                salary_max_k INTEGER,
                experience_min_years INTEGER,
                experience_max_years INTEGER,
                official_sources_only INTEGER NOT NULL DEFAULT 1,
                exclusions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
                    ON DELETE CASCADE,
                UNIQUE (workspace_id, name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_migrations "
            "(version, applied_at) "
            "VALUES ('0001_old_name', datetime('now'))"
        )

    # Should reconcile without error
    database.migrate()

    with database.connect() as conn:
        versions = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        index = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_search_plans_workspace'"
        ).fetchone()
    assert "0001_old_name" in versions
    assert "0001_workspace" in versions
    # Other migrations should also be applied (fresh tables)
    assert "0002_profiles" in versions
    assert index is not None


def test_partial_table_state_raises_conflict(tmp_path) -> None:
    """If only some tables from a migration exist, raise MigrationConflict."""
    database = Database(tmp_path / "jobfindsme.db")

    # 0001_workspace creates workspaces + search_plans.
    # Create only workspaces — not search_plans.
    with database.connect() as conn:
        conn.execute(
            """
            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

    with pytest.raises(MigrationConflict) as exc:
        database.migrate()
    assert "0001_workspace" in str(exc.value)
    assert "workspaces" in str(exc.value)
    assert "search_plans" in str(exc.value)


def test_reconcile_preserves_existing_data(tmp_path) -> None:
    """Reconciliation should not touch existing data in pre-existing tables."""
    database = Database(tmp_path / "jobfindsme.db")

    with database.connect() as conn:
        conn.execute(
            """
            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE search_plans (
                plan_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                target_roles_json TEXT NOT NULL,
                locations_json TEXT NOT NULL,
                salary_min_k INTEGER,
                salary_max_k INTEGER,
                experience_min_years INTEGER,
                experience_max_years INTEGER,
                official_sources_only INTEGER NOT NULL DEFAULT 1,
                exclusions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
                    ON DELETE CASCADE,
                UNIQUE (workspace_id, name)
            )
            """
        )
        conn.execute(
            "INSERT INTO workspaces "
            "(workspace_id, name, created_at) "
            "VALUES ('ws-1', 'test', '2026-01-01')"
        )
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

    database.migrate()

    with database.connect() as conn:
        rows = conn.execute("SELECT workspace_id, name FROM workspaces").fetchall()
    assert len(rows) == 1
    assert rows[0]["workspace_id"] == "ws-1"
    assert rows[0]["name"] == "test"


def test_same_table_names_with_missing_columns_raise_conflict(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")

    with database.connect() as conn:
        conn.execute(
            """
            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE search_plans (
                plan_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                target_roles_json TEXT NOT NULL,
                locations_json TEXT NOT NULL,
                exclusions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    with pytest.raises(MigrationConflict) as exc:
        database.migrate()

    message = str(exc.value)
    assert "0001_workspace" in message
    assert "search_plans" in message
    assert "missing columns" in message
    assert "official_sources_only" in message


def test_search_plan_requires_an_existing_workspace(tmp_path) -> None:
    database = Database(tmp_path / "jobfindsme.db")
    database.migrate()

    with database.connect() as connection:
        try:
            connection.execute(
                """
                INSERT INTO search_plans (
                    plan_id, workspace_id, name, target_roles_json,
                    locations_json, official_sources_only, exclusions_json,
                    created_at, updated_at
                ) VALUES (
                    'plan-1', 'missing', 'test', '["AI"]', '[]', 1, '[]',
                    '2026-07-28T00:00:00+00:00',
                    '2026-07-28T00:00:00+00:00'
                )
                """
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("foreign key violation should fail")


def test_database_directory_and_files_are_private_by_default(tmp_path) -> None:
    database = Database(tmp_path / "private" / "jobfindsme.db")

    with database.connect() as connection:
        connection.execute("CREATE TABLE privacy_probe (value TEXT)")

    directory_mode = stat.S_IMODE(database.path.parent.stat().st_mode)
    database_mode = stat.S_IMODE(database.path.stat().st_mode)
    assert directory_mode == 0o700
    assert database_mode == 0o600
