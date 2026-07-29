from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
    re.IGNORECASE,
)


class MigrationConflict(Exception):
    """Raised when migration tables exist in an inconsistent state."""


class Database:
    """Own SQLite connections and apply ordered, repeatable migrations."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        self._secure_sqlite_files()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
            self._secure_sqlite_files()

    def _secure_sqlite_files(self) -> None:
        for path in (
            self.path,
            Path(f"{self.path}-wal"),
            Path(f"{self.path}-shm"),
        ):
            if path.exists():
                try:
                    os.chmod(path, 0o600)
                except FileNotFoundError:
                    # SQLite may remove a WAL/SHM sidecar between exists() and
                    # chmod() while parallel connector threads close a handle.
                    if path == self.path:
                        raise

    @staticmethod
    def _table_names_from_sql(sql: str) -> set[str]:
        return set(_CREATE_TABLE_RE.findall(sql))

    @staticmethod
    def _existing_tables(connection: sqlite3.Connection, names: set[str]) -> set[str]:
        placeholders = ",".join("?" for _ in names)
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            f"WHERE type='table' AND name IN ({placeholders})",
            tuple(names),
        ).fetchall()
        return {row["name"] for row in rows}

    @staticmethod
    def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _column_signatures(
        connection: sqlite3.Connection,
        table_name: str,
    ) -> dict[str, tuple[str, bool, int]]:
        rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        return {
            row["name"]: (
                str(row["type"]).upper(),
                bool(row["notnull"]),
                int(row["pk"]),
            )
            for row in rows
        }

    def _validate_compatible_schema(
        self,
        connection: sqlite3.Connection,
        *,
        migration: str,
        sql: str,
        table_names: set[str],
    ) -> None:
        reference = sqlite3.connect(":memory:")
        reference.row_factory = sqlite3.Row
        try:
            reference.executescript(sql)
            for table_name in table_names:
                expected = self._column_signatures(reference, table_name)
                actual = self._column_signatures(connection, table_name)
                missing = sorted(set(expected) - set(actual))
                incompatible = sorted(
                    name
                    for name in expected.keys() & actual.keys()
                    if expected[name] != actual[name]
                )
                if missing or incompatible:
                    details = []
                    if missing:
                        details.append(f"missing columns {missing}")
                    if incompatible:
                        details.append(f"incompatible columns {incompatible}")
                    raise MigrationConflict(
                        f"Migration {migration} cannot reconcile table "
                        f"{table_name}: {', '.join(details)}. Restore from a "
                        "backup or migrate the old schema explicitly."
                    )
        finally:
            reference.close()

    def _execute_sql_safely(self, connection: sqlite3.Connection, sql: str) -> None:
        """Execute migration SQL, skipping CREATE TABLE/INDEX that already exist."""
        for statement in _split_sql_statements(sql):
            statement = statement.strip()
            if not statement:
                continue

            table_match = _CREATE_TABLE_RE.match(statement)
            if table_match:
                table_name = table_match.group(1)
                if self._existing_tables(connection, {table_name}):
                    continue
                connection.execute(statement)
                continue

            # Handle CREATE INDEX – check if index already exists
            idx_match = re.match(
                r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
                statement,
                re.IGNORECASE,
            )
            if idx_match:
                if self._index_exists(connection, idx_match.group(1)):
                    continue
                connection.execute(statement)
                continue

            # ALTER TABLE ADD COLUMN — skip if column already exists
            alter_match = re.match(
                r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+(?:COLUMN\s+)?(\w+)",
                statement,
                re.IGNORECASE,
            )
            if alter_match:
                table, column = alter_match.group(1), alter_match.group(2)
                cols = {
                    row[1]
                    for row in connection.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                }
                if column in cols:
                    continue

            connection.execute(statement)

    def migrate(self) -> None:
        migrations_dir = Path(__file__).with_name("migrations")
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                row["version"]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            for path in sorted(migrations_dir.glob("*.sql")):
                if path.stem in applied:
                    continue
                sql = path.read_text(encoding="utf-8")
                table_names = self._table_names_from_sql(sql)

                if table_names:
                    existing = self._existing_tables(connection, table_names)
                    if existing == table_names:
                        # A previous release may have used another migration
                        # version name. Table names alone are not enough: verify
                        # required columns before recording the new version.
                        self._validate_compatible_schema(
                            connection,
                            migration=path.stem,
                            sql=sql,
                            table_names=table_names,
                        )
                        # Re-run safely so missing explicit indexes are restored.
                        self._execute_sql_safely(connection, sql)
                        connection.execute(
                            "INSERT INTO schema_migrations "
                            "(version, applied_at) "
                            "VALUES (?, datetime('now'))",
                            (path.stem,),
                        )
                        continue
                    if existing:
                        missing = table_names - existing
                        raise MigrationConflict(
                            f"Migration {path.stem} is in an inconsistent state: "
                            f"tables {sorted(existing)} already exist, but "
                            f"tables {sorted(missing)} are missing. "
                            f"Restore from a backup or run 'jobfindsme delete' "
                            f"to reset the local database."
                        )

                self._execute_sql_safely(connection, sql)
                connection.execute(
                    "INSERT INTO schema_migrations "
                    "(version, applied_at) "
                    "VALUES (?, datetime('now'))",
                    (path.stem,),
                )


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL text into individual statements, skipping empty ones."""
    statements = []
    for statement in sql.split(";"):
        stripped = statement.strip()
        if stripped:
            statements.append(stripped)
    return statements
