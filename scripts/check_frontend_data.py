"""Validate frontend atlas_web_data.json before deployment.
Includes coordinate parsing, equirectangular projection tests."""

import json
import sys
from pathlib import Path

DATA_PATH = Path("frontend/public/data/atlas_web_data.json")
MAX_MB = 5
MIN_PLANTS = 1000


def get_lon(record: dict) -> float | None:
    v = record.get("lon")
    if v is None:
        v = record.get("longitude")
    if v is None:
        v = record.get("lng")
    if v is None:
        return None
    try:
        n = float(v)
        return n if (-180 <= n <= 180) else None
    except (ValueError, TypeError):
        return None


def get_lat(record: dict) -> float | None:
    v = record.get("lat")
    if v is None:
        v = record.get("latitude")
    if v is None:
        return None
    try:
        n = float(v)
        return n if (-90 <= n <= 90) else None
    except (ValueError, TypeError):
        return None


def equirectangular_x(lon: float, width: float) -> float:
    return ((lon + 180) / 360) * width


def equirectangular_y(lat: float, height: float) -> float:
    return ((90 - lat) / 180) * height


def cable_has_renderable_geometry(cable: dict) -> bool:
    geom = cable.get("geometry")
    if not geom:
        return False
    is_multi = isinstance(geom[0], list) and bool(geom[0]) and isinstance(geom[0][0], list)
    lines = geom if is_multi else [geom]
    for line in lines:
        valid_points = 0
        for coord in line:
            if not isinstance(coord, list) or len(coord) < 2:
                continue
            lon, lat = coord[0], coord[1]
            try:
                lon_f = float(lon)
                lat_f = float(lat)
            except (ValueError, TypeError):
                continue
            if -180 <= lon_f <= 180 and -90 <= lat_f <= 90:
                valid_points += 1
        if valid_points >= 2:
            return True
    return False


def main():
    errors = []
    warnings = []

    # --- Equirectangular projection tests ---
    W, H = 1200, 800
    assert equirectangular_x(-180, W) == 0, "equirectangular_x(-180) != 0"
    assert equirectangular_x(180, W) == W, "equirectangular_x(180) != width"
    assert equirectangular_x(0, W) == W / 2, "equirectangular_x(0) != center"
    assert equirectangular_y(90, H) == 0, "equirectangular_y(90) != 0"
    assert equirectangular_y(-90, H) == H, "equirectangular_y(-90) != height"
    assert equirectangular_y(0, H) == H / 2, "equirectangular_y(0) != center"
    print("[PROJ] Equirectangular projection tests: PASS")

    # --- get_lon / get_lat tests ---
    assert get_lon({"lon": 65.119}) == 65.119
    assert get_lon({"longitude": -74.006}) == -74.006
    assert get_lon({"lng": 103.8}) == 103.8
    assert get_lon({"lon": "32.5"}) == 32.5
    assert get_lon({}) is None
    assert get_lon({"lon": 999}) is None
    assert get_lat({"lat": 32.322}) == 32.322
    assert get_lat({"latitude": 40.7128}) == 40.7128
    assert get_lat({"lat": "31.67"}) == 31.67
    assert get_lat({}) is None
    assert get_lat({"lat": 999}) is None
    print("[PARSE] Coordinate parsing tests: PASS")

    # 1. File exists
    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} not found")
        sys.exit(1)

    size_bytes = DATA_PATH.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"File size: {size_mb:.2f} MB")

    if size_mb > MAX_MB:
        errors.append(f"File too large: {size_mb:.2f} MB > {MAX_MB} MB")

    # 2. Valid JSON
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON — {e}")
        sys.exit(1)

    # 3. Has key sections
    for key in ("metadata", "power_plants", "cables", "data_centers"):
        if key not in data:
            errors.append(f"Missing '{key}' key")

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

    if len(plants) < MIN_PLANTS:
        errors.append(f"Too few power plants: {len(plants)} < {MIN_PLANTS}")

    # 4. Validate coordinates using get_lon/get_lat (same logic as canvas renderer)
    valid_coords = 0
    invalid_coords = 0
    first_valid_sample = None
    for p in plants:
        lon = get_lon(p)
        lat = get_lat(p)
        if lon is not None and lat is not None:
            valid_coords += 1
            if first_valid_sample is None:
                first_valid_sample = (lon, lat, p.get("n", ""), p.get("f", ""))
        else:
            invalid_coords += 1

    print(f"Valid power plant coordinates: {valid_coords}")
    print(f"Invalid/missing coordinates: {invalid_coords}")

    if first_valid_sample:
        lon, lat, name, fuel = first_valid_sample
        proj_x = equirectangular_x(lon, 1200)
        proj_y = equirectangular_y(lat, 800)
        print(f"First valid sample: '{name}' lon={lon} lat={lat} fuel={fuel}")
        print(f"  Equirectangular on 1200x800: x={proj_x:.1f} y={proj_y:.1f}")

    if valid_coords < MIN_PLANTS:
        errors.append(f"Too few valid coordinates: {valid_coords} < {MIN_PLANTS}")

    # 5. Cables breakdown
    cables_mapped = sum(1 for c in cables if c.get("mapped_status") == "mapped")
    cables_unmapped = sum(1 for c in cables if c.get("mapped_status") == "unmapped")
    cables_with_geom = sum(1 for c in cables if cable_has_renderable_geometry(c))
    print(f"Cables mapped: {cables_mapped}")
    print(f"Cables unmapped: {cables_unmapped}")
    print(f"Cables with geometry: {cables_with_geom}")

    # 6. Data centers breakdown
    dcs_mapped = sum(1 for d in dcs if d.get("mapped_status") == "mapped")
    dcs_unmapped = sum(1 for d in dcs if d.get("mapped_status") == "unmapped")
    dcs_with_coords = sum(1 for d in dcs if get_lon(d) is not None and get_lat(d) is not None)
    print(f"Data centers mapped: {dcs_mapped}")
    print(f"Data centers unmapped: {dcs_unmapped}")
    print(f"Data centers with coords: {dcs_with_coords}")

    # 7. Counts consistency
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
