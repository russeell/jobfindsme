import sqlite3

from jobfindsme.storage import Database


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
    ]
    assert foreign_keys == 1


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
