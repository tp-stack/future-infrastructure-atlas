#!/usr/bin/env python3
"""Build a lightweight derived infrastructure index for site selection scoring.

Produces a compact JSON index (<10 MB) with:
  - Compact separators (no indentation)
  - Null fields dropped from every feature
  - Lat/lon rounded to 5 decimal places
  - Substation points from OSM (>=100 kV, spatially sampled if too dense)
  - HV line proxy points from OSM (>=100 kV line endpoints, sampled)
  - Power plant, data center, cable landing points from atlas_web_data.json
  - Spatial sampling by grid cell if index exceeds 10 MB limit
"""

import json
import math
from pathlib import Path
from datetime import datetime, timezone

MAX_INDEX_SIZE_BYTES = 10_000_000


def _round(v: float | None, decimals: int = 5) -> float | None:
    if v is None:
        return None
    return round(v, decimals)


def _drop_nulls(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _grid_cell_key(lat: float, lon: float, cell_deg: float) -> tuple[int, int]:
    return (int(math.floor(lat / cell_deg)), int(math.floor(lon / cell_deg)))


def _sample_by_grid(features: list[dict], cell_deg: float) -> list[dict]:
    seen_cells: set[tuple[int, int]] = set()
    sampled: list[dict] = []
    for f in features:
        key = _grid_cell_key(f.get("lat", 0), f.get("lon", 0), cell_deg)
        if key not in seen_cells:
            seen_cells.add(key)
            sampled.append(f)
    return sampled


def _parse_voltage(v: object) -> int:
    """Parse voltage to int, return 0 for unknown."""
    if v is None:
        return 0
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return 0


def _stream_substations(cache_dir: Path, min_voltage_kv: int = 100) -> list[dict]:
    """Stream substations NDJSON, filter by voltage, build compact features."""
    ndjson_path = cache_dir / "osm_global_power_grid" / "substations.ndjson"
    if not ndjson_path.exists():
        print(f"  WARNING: Substations NDJSON not found at {ndjson_path}")
        return []

    features: list[dict] = []
    total = 0
    kept = 0
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            props = obj.get("properties", {})
            coords = obj.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            voltage = _parse_voltage(props.get("voltage"))
            if voltage < min_voltage_kv:
                continue
            feat = _drop_nulls({
                "id": props.get("id"),
                "lat": _round(lat),
                "lon": _round(lon),
                "t": "ss",
                "q": "obs",
                "v": voltage,
                "c": props.get("country"),
                "name": props.get("n"),
            })
            features.append(feat)
            kept += 1

    print(f"  Substations: {total} total, {kept} >= {min_voltage_kv} kV")
    return features


def _stream_power_lines(cache_dir: Path, min_voltage_kv: int = 100) -> list[dict]:
    """Stream power lines NDJSON, filter by voltage, extract one point per line."""
    ndjson_path = cache_dir / "osm_global_power_grid" / "power_lines.ndjson"
    if not ndjson_path.exists():
        print(f"  WARNING: Power lines NDJSON not found at {ndjson_path}")
        return []

    features: list[dict] = []
    total = 0
    kept = 0
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            props = obj.get("properties", {})
            voltage = _parse_voltage(props.get("voltage"))
            if voltage < min_voltage_kv:
                continue
            geometry = obj.get("geometry", {})
            geom_type = geometry.get("type", "")
            coords_list = geometry.get("coordinates", [])
            if not coords_list:
                continue
            # Extract a representative point: start of the line
            if geom_type in ("LineString",):
                pts = coords_list
            elif geom_type in ("MultiLineString",):
                pts = coords_list[0] if coords_list else []
            else:
                continue
            if len(pts) < 2:
                continue
            # Use the first coordinate as the proxy point
            first = pts[0]
            if len(first) < 2:
                continue
            lon, lat = float(first[0]), float(first[1])
            feat = _drop_nulls({
                "id": props.get("id"),
                "lat": _round(lat),
                "lon": _round(lon),
                "t": "hv",
                "q": "der",
                "v": voltage,
                "c": props.get("country"),
            })
            features.append(feat)
            kept += 1

    print(f"  Power lines: {total} total, {kept} >= {min_voltage_kv} kV (one proxy point per line)")
    return features


def main():
    base_dir = Path(__file__).parent.parent
    frontend_data_dir = base_dir / "frontend" / "public" / "data"
    cache_dir = base_dir / "data" / "cache"
    output_dir = base_dir / "data" / "derived" / "site_selection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "infrastructure_index.json"

    source_files = ["atlas_web_data.json"]
    source_notes = {}
    all_features: dict[str, list[dict]] = {}

    # ── 1. Power plants from atlas_web_data.json ──
    atlas_path = frontend_data_dir / "atlas_web_data.json"
    if not atlas_path.exists():
        atlas_path = base_dir / "data" / "processed" / "web" / "atlas_web_data.json"

    print(f"Loading atlas data from: {atlas_path}")
    with open(atlas_path, "r", encoding="utf-8") as f:
        atlas_data = json.load(f)

    power_plants_raw = atlas_data.get("power_plants", [])
    data_centers_raw = atlas_data.get("data_centers", [])
    cables_raw = atlas_data.get("cables", [])

    print(f"Raw counts: {len(power_plants_raw)} power plants, {len(data_centers_raw)} data centers, {len(cables_raw)} cables")

    power_plant_features = []
    for pp in power_plants_raw:
        lat = pp.get("lat")
        lon = pp.get("lon")
        if lat is None or lon is None:
            continue
        f = _drop_nulls({
            "id": pp.get("n"),
            "lat": _round(lat),
            "lon": _round(lon),
            "t": "pp",
            "q": "obs",
            "c": pp.get("c"),
            "mw": pp.get("mw"),
            "name": pp.get("n"),
        })
        power_plant_features.append(f)

    data_center_features = []
    for dc in data_centers_raw:
        lat = dc.get("lat")
        lon = dc.get("lon")
        if lat is None or lon is None:
            continue
        f = _drop_nulls({
            "id": dc.get("n"),
            "lat": _round(lat),
            "lon": _round(lon),
            "t": "dc",
            "q": "obs",
            "c": dc.get("c"),
            "city": dc.get("city"),
            "name": dc.get("n"),
        })
        data_center_features.append(f)

    cable_features = []
    for cb in cables_raw:
        name = cb.get("n", "")
        geometry = cb.get("geometry", []) if isinstance(cb.get("geometry"), list) else []
        for line in geometry:
            if isinstance(line, list) and len(line) >= 2:
                first = line[0]
                last = line[-1]
                for pt in (first, last):
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        lon, lat = float(pt[0]), float(pt[1])
                        if lat is not None and lon is not None:
                            f = _drop_nulls({
                                "id": name,
                                "lat": _round(lat),
                                "lon": _round(lon),
                                "t": "cbl",
                                "q": "obs",
                            })
                            cable_features.append(f)

    print(f"Extracted {len(power_plant_features)} pp, {len(data_center_features)} dc, {len(cable_features)} cbl")
    source_files.append("atlas_web_data.json")
    source_notes["power_plants"] = "WRI Global Power Plant Database via atlas_web_data.json. Observed coordinates."
    source_notes["data_centers"] = "PeeringDB facilities via atlas_web_data.json. Observed coordinates."
    source_notes["cables"] = "Submarine cable landing points from atlas_web_data.json."

    all_features["power_plant_points"] = power_plant_features
    all_features["data_center_points"] = data_center_features
    all_features["cable_landing_points"] = cable_features

    # ── 2. Substation points from OSM NDJSON ──
    print("Streaming substations from OSM cache...")
    substation_features = _stream_substations(cache_dir, min_voltage_kv=100)
    source_files.append("osm_global_power_grid/substations.ndjson")
    source_notes["substations"] = (
        f"OSM substations >= 100 kV from osm_global_power_grid cache. "
        f"Observed coordinates with voltage_kv. {len(substation_features)} points extracted."
    )
    all_features["substation_points"] = substation_features

    # ── 3. High-voltage line proxy points from OSM NDJSON ──
    print("Streaming power lines from OSM cache...")
    hv_line_features = _stream_power_lines(cache_dir, min_voltage_kv=100)
    source_files.append("osm_global_power_grid/power_lines.ndjson")
    source_notes["high_voltage_lines"] = (
        f"OSM power lines >= 100 kV from osm_global_power_grid cache. "
        f"One proxy point per line (start of geometry). Derived, not observed coordinates. "
        f"{len(hv_line_features)} points extracted."
    )
    all_features["high_voltage_points"] = hv_line_features

    # ── Build index ──
    generated_at = datetime.now(timezone.utc).isoformat()
    feature_counts = {k: len(v) for k, v in all_features.items()}

    # Determine empty categories
    empty = [k for k, v in feature_counts.items() if v == 0]
    empty_msg = ""
    if empty:
        empty_msg = (
            f"The following categories have zero features: {', '.join(empty)}. "
            f"Grid and fiber scores based solely on proxies remain proxy estimates."
        )

    metadata = {
        "generated_at": generated_at,
        "source_files": list(dict.fromkeys(source_files)),  # dedup preserving order
        "source_notes": source_notes,
        "feature_counts": feature_counts,
    }
    if empty_msg:
        metadata["empty_categories_warning"] = empty_msg

    index = {
        "metadata": metadata,
        "features": all_features,
    }

    raw = json.dumps(index, separators=(",", ":"), ensure_ascii=False)
    size = len(raw.encode("utf-8"))
    print(f"\nIndex size before sampling: {size} bytes ({size/1024/1024:.1f} MB)")

    # ── If too large, spatially sample starting with lowest priority categories ──
    if size > MAX_INDEX_SIZE_BYTES:
        print(f"Index exceeds {MAX_INDEX_SIZE_BYTES} bytes, applying spatial sampling...")

        # Priority order: sample HV lines first (largest category) with coarser cell,
        # then substations, then cables, then power plants last (prefer keeping them).
        sampling_cells = [
            ("high_voltage_points", 0.5),
            ("substation_points", 0.25),
            ("cable_landing_points", 0.25),
            ("power_plant_points", 0.25),
        ]

        for cat_name, cell_size in sampling_cells:
            if size <= MAX_INDEX_SIZE_BYTES:
                break
            if cat_name not in index["features"] or not index["features"][cat_name]:
                continue
            current = index["features"][cat_name]
            sampled = _sample_by_grid(current, cell_size)
            old_count = len(current)
            if len(sampled) < old_count:
                index["features"][cat_name] = sampled
                feature_counts[cat_name] = len(sampled)
                print(f"  Sampled {cat_name} at {cell_size} deg: {len(sampled)} (from {old_count})")
                raw = json.dumps(index, separators=(",", ":"), ensure_ascii=False)
                size = len(raw.encode("utf-8"))
                print(f"  New index size: {size} bytes ({size/1024/1024:.1f} MB)")

        index["metadata"]["feature_counts"] = feature_counts
        index["metadata"]["sampling_note"] = (
            f"Spatial sampling applied (HV lines at 0.5 deg, others at 0.25 deg grid cell) "
            f"to stay within the {MAX_INDEX_SIZE_BYTES} byte limit."
        )
        raw = json.dumps(index, separators=(",", ":"), ensure_ascii=False)
        size = len(raw.encode("utf-8"))

    print(f"Final index size: {size} bytes ({size/1024/1024:.1f} MB)")

    with open(output_path, "wb") as f:
        f.write(raw.encode("utf-8"))
    print(f"Infrastructure index written to: {output_path}")

    # ── Write human-readable summary ──
    summary_path = output_dir / "index_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Infrastructure Index Summary\n")
        f.write(f"Generated at: {generated_at}\n")
        f.write(f"Source files: {', '.join(index['metadata']['source_files'])}\n")
        f.write(f"Final size: {size} bytes ({size/1024/1024:.1f} MB)\n")
        f.write(f"Feature counts:\n")
        for k, v in feature_counts.items():
            f.write(f"  {k}: {v}\n")
        total = sum(feature_counts.values())
        f.write(f"Total features: {total}\n")
        if index["metadata"].get("sampling_note"):
            f.write(f"\nSampling note: {index['metadata']['sampling_note']}\n")
        if empty:
            f.write(f"\nEmpty categories: {', '.join(empty)}\n")
        f.write(f"\nGrid scores use substation_points > high_voltage_points > power_plant_points.\n")
        f.write(f"GRID_CAPACITY_UNKNOWN remains flagged unless real utility capacity is confirmed.\n")

    print(f"Summary written to: {summary_path}")
    print(f"\nFeature counts: {json.dumps(feature_counts, indent=2)}")
    print(f"Empty categories: {empty if empty else 'none'}")


if __name__ == "__main__":
    main()