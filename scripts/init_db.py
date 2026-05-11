"""Initialize the local PostGIS database schema and seed records."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.db import run_sql_file, wait_for_database  # noqa: E402


SQL_FILES = [
    PROJECT_ROOT / "database" / "migrations" / "001_initial_schema.sql",
    PROJECT_ROOT / "database" / "seeds" / "001_seed_sources.sql",
    PROJECT_ROOT / "database" / "migrations" / "002_dataset_registry.sql",
    PROJECT_ROOT / "database" / "seeds" / "002_seed_datasets.sql",
]


def main() -> int:
    wait_for_database(timeout_seconds=30)
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
