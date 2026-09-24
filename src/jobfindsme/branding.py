"""Public product identifiers and compatibility paths.

The Python import namespace stays ``jobfindsme`` during the rename window so
existing integrations keep importing the same modules. Everything users see
uses Agent Job Search / agent-job-search.
"""

from __future__ import annotations

import os
from pathlib import Path

DISPLAY_NAME = "Agent Job Search"
SLUG = "agent-job-search"
DISTRIBUTION_NAME = "agent-job-search"
REPOSITORY = "russeell/agent-job-search"

LEGACY_SLUG = "jobfindsme"
DB_ENV = "AGENT_JOB_SEARCH_DB_PATH"
LEGACY_DB_ENV = "JOBFINDSME_DB_PATH"


def data_root(home: Path | None = None) -> Path:
    """Use the new data root, falling back to a populated legacy install."""
    home = home or Path.home()
    current = home / f".{SLUG}"
    legacy = home / f".{LEGACY_SLUG}"
    current_user_data = any(
        path.exists()
        for path in (
            current / "data" / "agent-job-search.db",
            current / "data" / "jobfindsme.db",
            current / "chrome-profile",
        )
    )
    legacy_user_data = any(
        path.exists()
        for path in (
            legacy / "data" / "jobfindsme.db",
            legacy / "chrome-profile",
        )
    )
    if legacy_user_data and not current_user_data:
        return legacy
    return current


def database_path(home: Path | None = None) -> Path:
    override = os.getenv(DB_ENV) or os.getenv(LEGACY_DB_ENV)
    if override:
        return Path(override).expanduser()
    root = data_root(home)
    legacy_database = root / "data" / "jobfindsme.db"
    current_database = root / "data" / "agent-job-search.db"
    if legacy_database.exists() and not current_database.exists():
        return legacy_database
    return current_database


def runtime_python(home: Path | None = None) -> Path:
    home = home or Path.home()
    current = home / f".{SLUG}" / "runtime" / "bin" / "python"
    legacy = home / f".{LEGACY_SLUG}" / "runtime" / "bin" / "python"
    if current.is_file() or not legacy.is_file():
        return current
    return legacy
