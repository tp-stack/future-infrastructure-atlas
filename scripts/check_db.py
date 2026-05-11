"""Check local PostGIS database health."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.db import fetch_one  # noqa: E402
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

    try:
        row = fetch_one("SELECT current_database() AS database_name")
        print(f"connection: ok ({row['database_name']})")
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
        source_count = count_rows("dim_source")
        print(f"sources: {source_count}")
        if source_count < 10:
            failures.append("Initial source seed rows are missing.")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Source seed check failed: {exc}")
        print(f"sources: failed ({exc})")

    try:
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
