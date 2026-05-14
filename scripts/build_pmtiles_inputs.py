"""Generate GeoJSON input files for tippecanoe from the current atlas data.

Outputs:
  data/cache/pmtiles/power_plants.geojson
  data/cache/pmtiles/submarine_cables.geojson
  data/cache/pmtiles/data_centers.geojson
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "pmtiles"


def _valid_coord_pair(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def generate_power_plants(data: dict) -> dict:
    features = []
    for pp in data.get("power_plants", []):
        lat = pp.get("lat")
        lon = pp.get("lon")
        if lat is None or lon is None:
            continue
        if not _valid_coord_pair(lon, lat):
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "n": pp.get("n", ""),
                "c": pp.get("c", ""),
                "f": pp.get("f", ""),
                "mw": pp.get("mw", 0),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def generate_submarine_cables(data: dict) -> dict:
    features = []
    for cable in data.get("cables", []):
        if cable.get("mapped_status") != "mapped":
            continue
        geom = cable.get("geometry")
        if not geom:
            continue
        is_multi = isinstance(geom[0], list) and geom[0] and isinstance(geom[0][0], list)
        if is_multi:
            gtype = "MultiLineString"
            coords = [line for line in geom if isinstance(line, list) and len(line) >= 2]
            if not coords:
                continue
        else:
            if len(geom) < 2:
                continue
            gtype = "LineString"
            coords = geom
        features.append({
            "type": "Feature",
            "geometry": {"type": gtype, "coordinates": coords},
            "properties": {
                "n": cable.get("n", ""),
                "source": cable.get("source", ""),
                "source_license": cable.get("source_license", ""),
                "geometry_precision": cable.get("geometry_precision", ""),
                "confidence": cable.get("confidence", 0),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def generate_data_centers(data: dict) -> dict:
    features = []
    for dc in data.get("data_centers", []):
        if dc.get("mapped_status") != "mapped":
            continue
        lat = dc.get("lat")
        lon = dc.get("lon")
        if lat is None or lon is None:
            continue
        if not _valid_coord_pair(lon, lat):
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "n": dc.get("n", ""),
                "op": dc.get("op", ""),
                "c": dc.get("c", ""),
                "city": dc.get("city", ""),
                "coordinate_precision": dc.get("coordinate_precision", ""),
                "source_license": dc.get("source_license", ""),
                "confidence": dc.get("confidence", 0),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def load_frontend_data() -> dict | None:
    path = PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_web_data.json"
    if not path.exists():
        print(f"ERROR: {path} not found. Run build_web_map_data.py first.", file=sys.stderr)
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    data = load_frontend_data()
    if data is None:
        sys.exit(1)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    layers = [
        ("power_plants", generate_power_plants),
        ("submarine_cables", generate_submarine_cables),
        ("data_centers", generate_data_centers),
    ]

    for name, gen_fn in layers:
        fc = gen_fn(data)
        out_path = CACHE_DIR / f"{name}.geojson"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False)
        print(f"[pmtiles-inputs] {name}: {len(fc['features'])} features -> {out_path}")

    print("\n[pmtiles-inputs] All input GeoJSON files generated in data/cache/pmtiles/")


if __name__ == "__main__":
    main()
