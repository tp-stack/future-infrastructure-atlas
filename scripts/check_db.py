"""Check database health against the configured schema."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas import settings  # noqa: E402
from atlas.db import check_health, fetch_one, fetch_all  # noqa: E402
from atlas.loaders.postgis import count_rows, postgis_available, table_exists  # noqa: E402


REQUIRED_TABLES = [
    "dim_source",
    "dim_country",
    "dim_operator",
    "infra_asset",
    "energy_asset",
    "telecom_asset",
    "resource_asset",
    "region_score",
    "ingestion_log",
    "asset_relationship",
    "dim_dataset",
    "dataset_manifest",
]


def main() -> int:
    failures: list[str] = []
    schema = settings.database_schema
    print(f"target schema: {schema}")

    # Lightweight health check via SELECT now()
    health = check_health()
    print(f"SELECT now() health: {health.get('status')} ({health.get('server_time', 'N/A')})")
    if health.get("status") != "ok":
        print(f"connection: failed ({health.get('message')})")
        return 1

    try:
        row = fetch_one("SELECT current_database() AS database_name, current_schema() AS current_schema")
        print(f"connection: ok (db={row['database_name']}, schema={row['current_schema']})")
    except Exception as exc:  # noqa: BLE001 - CLI should report concise health
        print(f"connection: failed ({exc})")
        return 1

    try:
        if postgis_available():
            print("postgis: ok")
        else:
            failures.append("PostGIS extension is not enabled.")
            print("postgis: missing")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"PostGIS check failed: {exc}")
        print(f"postgis: failed ({exc})")

    # List tables in the target schema
    try:
        rows = fetch_all(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (schema,),
        )
        existing_tables = [r["table_name"] for r in rows]
        print(f"tables in schema '{schema}': {existing_tables}")
    except Exception as exc:  # noqa: BLE001
        print(f"table listing: failed ({exc})")

    for table in REQUIRED_TABLES:
        try:
            if table_exists(table):
                print(f"table {table}: ok")
            else:
                failures.append(f"Required table is missing: {table}")
                print(f"table {table}: missing")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Table check failed for {table}: {exc}")
            print(f"table {table}: failed ({exc})")

    try:
        if table_exists("dim_source"):
            source_count = count_rows("dim_source")
            print(f"sources: {source_count}")
            if source_count < 10:
                failures.append("Initial source seed rows are missing.")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Source seed check failed: {exc}")
        print(f"sources: failed ({exc})")

    try:
        if table_exists("dim_dataset"):
            dataset_count = count_rows("dim_dataset")
            print(f"datasets: {dataset_count}")
            if dataset_count < 13:
                failures.append("Initial dataset seed rows are missing.")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Dataset seed check failed: {exc}")
        print(f"datasets: failed ({exc})")

    if failures:
        for failure in failures:
            print(f"failure: {failure}")
        return 1

    print("database health: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
