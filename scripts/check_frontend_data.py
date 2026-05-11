"""Validate frontend atlas_web_data.json before deployment."""

import json
import sys
from pathlib import Path

DATA_PATH = Path("frontend/public/data/atlas_web_data.json")
MAX_MB = 5
MIN_PLANTS = 1000


def main():
    errors = []
    warnings = []

    # 1. File exists
    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} not found")
        sys.exit(1)

    size_bytes = DATA_PATH.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"File size: {size_mb:.2f} MB")

    # 2. Under 5 MB
    if size_mb > MAX_MB:
        errors.append(f"File too large: {size_mb:.2f} MB > {MAX_MB} MB")

    # 3. Valid JSON
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON — {e}")
        sys.exit(1)

    # 4. Has key sections
    if "metadata" not in data:
        errors.append("Missing 'metadata' key")
    if "power_plants" not in data:
        errors.append("Missing 'power_plants' key")
    if "cables" not in data:
        errors.append("Missing 'cables' key")
    if "data_centers" not in data:
        errors.append("Missing 'data_centers' key")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    plants = data["power_plants"]
    cables = data["cables"]
    dcs = data["data_centers"]

    print(f"Power plants: {len(plants)}")
    print(f"Cables: {len(cables)}")
    print(f"Data centers: {len(dcs)}")

    # 5. Power plants > 1000
    if len(plants) < MIN_PLANTS:
        errors.append(f"Too few power plants: {len(plants)} < {MIN_PLANTS}")

    # 6. Valid lon/lat
    valid_coords = 0
    invalid_coords = 0
    for p in plants:
        lon, lat = p.get("lon"), p.get("lat")
        if lon is not None and lat is not None and -180 <= lon <= 180 and -90 <= lat <= 90:
            valid_coords += 1
        else:
            invalid_coords += 1

    print(f"Valid power plant coordinates: {valid_coords}")
    print(f"Invalid/missing coordinates: {invalid_coords}")

    if valid_coords < MIN_PLANTS:
        errors.append(f"Too few valid coordinates: {valid_coords} < {MIN_PLANTS}")

    # 7. Cables breakdown
    cables_mapped = sum(1 for c in cables if c.get("mapped_status") == "mapped")
    cables_unmapped = sum(1 for c in cables if c.get("mapped_status") == "unmapped")
    cables_with_geom = sum(1 for c in cables if c.get("geometry") and len(c["geometry"]) >= 2)
    print(f"Cables mapped: {cables_mapped}")
    print(f"Cables unmapped: {cables_unmapped}")
    print(f"Cables with geometry: {cables_with_geom}")

    # 8. Data centers breakdown
    dcs_mapped = sum(1 for d in dcs if d.get("mapped_status") == "mapped")
    dcs_unmapped = sum(1 for d in dcs if d.get("mapped_status") == "unmapped")
    dcs_with_coords = sum(1 for d in dcs if d.get("lat") is not None and d.get("lon") is not None)
    print(f"Data centers mapped: {dcs_mapped}")
    print(f"Data centers unmapped: {dcs_unmapped}")
    print(f"Data centers with coords: {dcs_with_coords}")

    # 9. Counts consistency
    counts = data.get("metadata", {}).get("counts", {})
    if counts.get("power_plants_total") is not None and counts["power_plants_total"] != len(plants):
        warnings.append(f"Count mismatch: metadata.power_plants_total={counts['power_plants_total']} != actual={len(plants)}")
    if counts.get("power_plants_mapped") is not None and counts["power_plants_mapped"] != valid_coords:
        warnings.append(f"Count mismatch: metadata.power_plants_mapped={counts['power_plants_mapped']} != valid_coords={valid_coords}")

    for w in warnings:
        print(f"WARN: {w}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    print(f"\nPASS: {DATA_PATH} is valid ({size_mb:.2f} MB, {len(plants)} power plants, {valid_coords} with coords)")


if __name__ == "__main__":
    main()
