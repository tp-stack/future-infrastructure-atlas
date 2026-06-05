"""Initialize the database schema and seed records in the configured schema."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas import settings  # noqa: E402
from atlas.db import psycopg, fetch_one, get_connection, run_sql_file, wait_for_database  # noqa: E402


SQL_FILES = [
    PROJECT_ROOT / "database" / "migrations" / "001_initial_schema.sql",
    PROJECT_ROOT / "database" / "seeds" / "001_seed_sources.sql",
    PROJECT_ROOT / "database" / "migrations" / "002_dataset_registry.sql",
    PROJECT_ROOT / "database" / "seeds" / "002_seed_datasets.sql",
    PROJECT_ROOT / "database" / "migrations" / "003_commercial_api.sql",
    PROJECT_ROOT / "database" / "migrations" / "004_stripe_billing.sql",
]


def main() -> int:
    schema = settings.database_schema
    print(f"target schema: {schema}")

    wait_for_database(timeout_seconds=30)

    postgis_available = fetch_one(
        "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis') AS available"
    )
    if not postgis_available or not postgis_available["available"]:
        print("postgis: unavailable in this PostgreSQL server")
        print("Atlas full schema initialization requires PostGIS for GEOMETRY columns and spatial indexes.")
        print("Use a PostGIS-capable PostgreSQL server or add a non-PostGIS initialization path before running init_db.py.")
        return 1

    # Ensure the target schema exists and set search_path for all migrations.
    # App database roles such as role_atlas can create objects inside their
    # assigned schema, but should not need database-level CREATE SCHEMA rights.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                (schema,),
            )
            schema_exists = bool(cur.fetchone()["exists"])
            if not schema_exists:
                cur.execute(
                    psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
                )
            cur.execute(
                psycopg.sql.SQL("SET search_path TO {}, public").format(psycopg.sql.Identifier(schema))
            )
        conn.commit()
    print(f"schema '{schema}' is ready")

    for sql_file in SQL_FILES:
        if not sql_file.exists():
            print(f"skipped missing SQL file: {sql_file}")
            continue
        run_sql_file(sql_file)
        print(f"ran SQL file: {sql_file}")

    print("Database schema and registry seeds initialized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
