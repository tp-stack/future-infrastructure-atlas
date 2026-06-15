"""Check materialized Future Dataset Engine tables available to Atlas."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas import settings  # noqa: E402
from atlas.db import check_health  # noqa: E402
from atlas.loaders.cable_landing_points import cable_landing_point_loader_status  # noqa: E402
from atlas.loaders.data_centers import data_center_loader_status  # noqa: E402
from atlas.loaders.fde_tables import (  # noqa: E402
    configured_table_status,
    list_fde_tables,
    preview_fde_table,
)
from atlas.loaders.postgis import postgis_available  # noqa: E402
from atlas.loaders.power_plants import power_plant_loader_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect FDE materialized tables visible to Atlas.")
    parser.add_argument("--table", default=settings.atlas_fde_primary_table or settings.atlas_fde_data_centers_table)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    health = check_health()
    print(f"active database: {health.get('database')}")
    print(f"active schema: {health.get('schema')}")
    print(f"connection: {health.get('status')}")
    if health.get("status") != "ok":
        print(f"failure: {health.get('message')}")
        return 1

    print(f"postgis: {'available' if postgis_available() else 'missing'}")

    tables = list_fde_tables()
    print("available materialized tables:")
    for table in tables:
        print(f"  - {table['table_name']}: {table['row_count']} rows")

    print("configured table status:")
    for key, status in configured_table_status().items():
        print(f"  - {key}: {status}")
    print(f"fallback to local: {settings.atlas_fde_fallback_to_local}")

    if args.table:
        preview = preview_fde_table(args.table, limit=args.limit)
        print(f"preview table: {preview['table_name']}")
        print(f"preview row_count: {preview['row_count']}")
        print(f"preview columns: {[column['column_name'] for column in preview['columns']]}")
        print(f"preview sample_rows: {preview['sample_rows'][: args.limit]}")

    loader = data_center_loader_status()
    print("data center loader:")
    print(f"  source: {loader['source']}")
    print(f"  table_name: {loader.get('table_name')}")
    print(f"  source_path: {loader.get('source_path')}")
    print(f"  count: {loader['count']}")
    print(f"  mapped: {loader['mapped']}")
    print(f"  unmapped: {loader['unmapped']}")
    print(f"  fallback_enabled: {loader.get('fallback_enabled')}")
    print(f"  fallback_reason: {loader.get('fallback_reason')}")

    power_loader = power_plant_loader_status()
    print("power plant loader:")
    print(f"  source: {power_loader['source']}")
    print(f"  table_name: {power_loader.get('table_name')}")
    print(f"  source_path: {power_loader.get('source_path')}")
    print(f"  count: {power_loader['count']}")
    print(f"  mapped: {power_loader['mapped']}")
    print(f"  unmapped: {power_loader['unmapped']}")
    print(f"  fallback_enabled: {power_loader.get('fallback_enabled')}")
    print(f"  fallback_reason: {power_loader.get('fallback_reason')}")

    cable_loader = cable_landing_point_loader_status()
    print("cable landing point loader:")
    print(f"  source: {cable_loader['source']}")
    print(f"  table_name: {cable_loader.get('table_name')}")
    print(f"  source_path: {cable_loader.get('source_path')}")
    print(f"  count: {cable_loader['count']}")
    print(f"  mapped: {cable_loader['mapped']}")
    print(f"  unmapped: {cable_loader['unmapped']}")
    print(f"  fallback_enabled: {cable_loader.get('fallback_enabled')}")
    print(f"  fallback_reason: {cable_loader.get('fallback_reason')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
