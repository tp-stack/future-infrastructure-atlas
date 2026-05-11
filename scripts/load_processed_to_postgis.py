"""Load processed JSONL records into PostGIS if the database is available."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.ingestion.postgis_load import load_processed_to_postgis  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Load processed JSONL records into PostGIS.")
    parser.add_argument("--processed-path", required=True)
    args = parser.parse_args()

    processed_path = Path(args.processed_path)
    if not processed_path.is_absolute():
        processed_path = PROJECT_ROOT / processed_path
    if not processed_path.exists():
        print(f"error: processed file not found: {processed_path}")
        return 1

    result = load_processed_to_postgis(processed_path)

    if result.get("skipped"):
        print(f"Skipped: {result.get('reason', 'PostGIS unavailable')}")
        return 0

    if not result["ok"]:
        print(f"error: {result.get('error', 'unknown error')}")
        for err in result.get("errors", []):
            print(f"error: {err}")
        return 1

    print(f"records_loaded: {result['records_loaded']}")
    if result.get("records_failed"):
        print(f"records_failed: {result['records_failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
