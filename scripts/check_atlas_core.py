"""Validate atlas_core.json.

Checks:
- atlas_core.json exists
- contains counts
- contains tile URLs
- file size small, preferably < 500 KB
- does not contain heavy coordinate arrays
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_core.json"

MAX_SIZE_KB = 500

HEAVY_KEYS = ["power_plants", "cables", "data_centers"]


def check_atlas_core() -> int:
    errors = 0

    if not CORE_PATH.exists():
        print(f"FAIL: atlas_core.json not found at {CORE_PATH}")
        return 1

    size_kb = CORE_PATH.stat().st_size / 1024
    print(f"  Size: {size_kb:.1f} KB")

    if size_kb > MAX_SIZE_KB:
        print(f"  FAIL: Size {size_kb:.1f} KB exceeds {MAX_SIZE_KB} KB limit")
        errors += 1
    else:
        print(f"  OK: Size within {MAX_SIZE_KB} KB limit")

    try:
        with open(CORE_PATH, encoding="utf-8") as f:
            core = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  FAIL: Cannot parse atlas_core.json: {e}")
        return 1

    required_keys = ["generated_at", "architecture", "counts", "sources", "disclaimer", "tile_registry"]
    for key in required_keys:
        if key not in core:
            print(f"  FAIL: Missing required key '{key}'")
            errors += 1
        else:
            print(f"  OK: Has key '{key}'")

    for hk in HEAVY_KEYS:
        if hk in core:
            print(f"  FAIL: Contains heavy key '{hk}' — core must not include coordinate arrays")
            errors += 1
        else:
            print(f"  OK: No heavy array '{hk}'")

    tile_registry = core.get("tile_registry", {})
    for key in ["power_plants", "submarine_cables", "data_centers"]:
        entry = tile_registry.get(key)
        if entry is None:
            print(f"  FAIL: tile_registry missing entry '{key}'")
            errors += 1
            continue
        if "url" not in entry:
            print(f"  FAIL: tile_registry['{key}'] missing 'url'")
            errors += 1
        if "status" not in entry:
            print(f"  FAIL: tile_registry['{key}'] missing 'status'")
            errors += 1
        else:
            print(f"  OK: tile_registry['{key}'] status: {entry['status']}")

    counts = core.get("counts", {})
    count_keys = ["power_plants_mapped", "submarine_cables_mapped", "data_centers_mapped"]
    for ck in count_keys:
        if ck not in counts:
            print(f"  WARN: counts missing '{ck}'")
        else:
            print(f"  OK: counts['{ck}'] = {counts[ck]}")

    print()
    if errors:
        print(f"atlas_core.json validation: {errors} error(s)")
    else:
        print("atlas_core.json validation: PASSED")

    return errors


def main() -> None:
    errors = check_atlas_core()
    sys.exit(errors)


if __name__ == "__main__":
    main()
