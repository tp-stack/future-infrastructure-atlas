"""Simplify WRI Aqueduct GeoJSON for PMTiles build."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

src = PROJECT_ROOT / "data" / "cache" / "wri_aqueduct_baseline_annual.geojson"
fc = json.loads(src.read_text(encoding="utf-8"))
print(f"Input: {len(fc['features'])} features")

out = {"type": "FeatureCollection", "features": []}
for feat in fc["features"]:
    props = feat.get("properties", {})
    geom = feat.get("geometry")
    out["features"].append({
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "id": props.get("OBJECTID"),
            "sid": props.get("string_id"),
            "wr": props.get("w_awr_def_tot_cat"),
            "bws": props.get("bws_cat"),
            "bwd": props.get("bwd_cat"),
        },
    })

for feat in out["features"]:
    g = feat["geometry"]
    if not g:
        continue
    if g["type"] == "Polygon":
        for ring in g["coordinates"]:
            for pt in ring:
                pt[0] = round(pt[0], 3)
                pt[1] = round(pt[1], 3)
    elif g["type"] == "MultiPolygon":
        for poly in g["coordinates"]:
            for ring in poly:
                for pt in ring:
                    pt[0] = round(pt[0], 3)
                    pt[1] = round(pt[1], 3)

text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
raw_mb = len(text) / 1024 / 1024
print(f"Output: {len(out['features'])} features, {raw_mb:.1f} MB raw")

dst = PROJECT_ROOT / "data" / "cache" / "pmtiles" / "water_risk.geojson"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(text, encoding="utf-8")
print(f"Wrote {dst}")
