from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


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
                os.chmod(path, 0o600)

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
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, applied_at)
                    VALUES (?, datetime('now'))
                    """,
                    (path.stem,),
                )
