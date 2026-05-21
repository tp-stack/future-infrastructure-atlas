"""Validate PMTiles output files.

Checks:
- frontend/public/tiles/*.pmtiles only when explicitly served
- data/tiles/*.pmtiles build artifacts
- prints file sizes
- fails if public files exceed threshold
- does not require raw data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TILES = PROJECT_ROOT / "frontend" / "public" / "tiles"
DATA_TILES = PROJECT_ROOT / "data" / "tiles"

EXPECTED_TILES = [
    "power_plants.pmtiles",
    "submarine_cables.pmtiles",
    "data_centers.pmtiles",
    "power_lines.pmtiles",
    "substations.pmtiles",
]


def check_pmtiles(max_public_mb: float = 250) -> int:
    errors = 0
    max_bytes = int(max_public_mb * 1024 * 1024)

    print(f"Checking public PMTiles in: {FRONTEND_TILES}")
    print(f"Checking artifact PMTiles in: {DATA_TILES}")
    print(f"Max public size: {max_public_mb} MB ({max_bytes} bytes)")
    print()

    for name in EXPECTED_TILES:
        frontend_path = FRONTEND_TILES / name
        data_path = DATA_TILES / name

        if frontend_path.exists():
            size = frontend_path.stat().st_size
            size_mb = size / (1024 * 1024)
            if size > max_bytes:
                print(f"  FAIL: {name} is {size_mb:.2f} MB > {max_public_mb} MB limit")
                errors += 1
            else:
                print(f"  OK: {name} present in frontend/public/tiles/ ({size_mb:.2f} MB)")
        elif data_path.exists():
            size = data_path.stat().st_size
            size_mb = size / (1024 * 1024)
            print(f"  INFO: {name} in data/tiles/ ({size_mb:.2f} MB) - needs object storage/public deployment copy")
        else:
            print(f"  WARN: {name} not found - run build_pmtiles.py to generate")

    print()
    if errors:
        print(f"PMTiles validation: {errors} file(s) exceed the public size limit")
    else:
        print("PMTiles validation: PASSED")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Check PMTiles output files")
    parser.add_argument("--max-public-mb", type=float, default=250, help="Max MB per PMTiles (default: 250)")
    args = parser.parse_args()

    errors = check_pmtiles(args.max_public_mb)
    sys.exit(errors)


if __name__ == "__main__":
    main()
