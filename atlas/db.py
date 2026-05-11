"""PostGIS database utilities."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from atlas import settings

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - exercised only when dependency is absent or incomplete
    psycopg = None
    dict_row = None
    PSYCOPG_IMPORT_ERROR = exc
else:
    PSYCOPG_IMPORT_ERROR = None


def get_database_url() -> str:
    """Return the configured PostgreSQL connection URL."""

    return settings.database_url


def _require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError(
            "psycopg is not available. Install project dependencies with the psycopg binary extra "
            "before using database utilities."
        ) from PSYCOPG_IMPORT_ERROR


def get_connection():
    """Open a psycopg connection using dict rows."""

    _require_psycopg()
    return psycopg.connect(get_database_url(), row_factory=dict_row)


def wait_for_database(timeout_seconds: int = 30) -> bool:
    """Wait until the database accepts a simple query."""

    _require_psycopg()
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return True
        except Exception as exc:  # noqa: BLE001 - retry loop reports after timeout
            last_error = exc
            time.sleep(1)

    if last_error is not None:
        raise TimeoutError(f"Database did not become available within {timeout_seconds} seconds: {last_error}") from last_error
    raise TimeoutError(f"Database did not become available within {timeout_seconds} seconds.")


def run_sql_file(path: str | Path) -> None:
    """Execute a SQL file in one transaction."""

    sql = Path(path).read_text(encoding="utf-8")
    run_sql(sql)


def run_sql(sql: str, params: Any | None = None) -> None:
    """Execute SQL that does not need to return rows."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
        connection.commit()


def fetch_one(sql: str, params: Any | None = None) -> dict[str, Any] | None:
    """Fetch a single row as a dictionary."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()


def fetch_all(sql: str, params: Any | None = None) -> list[dict[str, Any]]:
    """Fetch all rows as dictionaries."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
