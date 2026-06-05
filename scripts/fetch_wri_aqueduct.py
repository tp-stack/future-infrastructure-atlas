"""Fetch WRI Aqueduct 4.0 Baseline Annual water risk polygons from ArcGIS Living Atlas.

Outputs a simplified GeoJSON that can be converted to PMTiles via build_pmtiles.py.

Source: https://www.arcgis.com/home/item.html?id=c784f4ebddaf43c8b816612fb62e7e5b
License: CC BY 4.0
"""

from __future__ import annotations

import io
import json
import sys
import time
import zlib
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "cache"

FEATURE_SERVICE = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services"
    "/aqueduct_water_risk/FeatureServer/1/query"
)

OUT_FIELDS = [
    "OBJECTID",
    "string_id",
    "name_0",
    "name_1",
    "bws_cat",
    "bwd_cat",
    "w_awr_def_tot_cat",
    "w_awr_def_tot_score",
    "bws_score",
    "bwd_score",
]

MAX_RECORDS = 750
DELAY = 0.5


def fetch_page(offset: int, out_format: str = "geojson") -> dict | None:
    params = {
        "where": "1=1",
        "outFields": ",".join(OUT_FIELDS),
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": str(offset),
        "resultRecordCount": str(MAX_RECORDS),
        "f": out_format,
    }
    resp = requests.get(FEATURE_SERVICE, params=params, timeout=60)
    resp.raise_for_status()
    if out_format == "geojson":
        return resp.json()
    return resp.json()


def simplify_geojson(fc: dict) -> dict:
    """Drop unnecessary properties and reduce coordinate precision."""
    for feat in fc.get("features", []):
        props = feat.get("properties", {})
        feat["properties"] = {k: props.get(k) for k in OUT_FIELDS if k in props}
        geom = feat.get("geometry")
        if geom and geom.get("type") == "Polygon":
            for ring in geom.get("coordinates", []):
                for pt in ring:
                    if len(pt) >= 2:
                        pt[0] = round(pt[0], 4)
                        pt[1] = round(pt[1], 4)
        elif geom and geom.get("type") == "MultiPolygon":
            for poly in geom.get("coordinates", []):
                for ring in poly:
                    for pt in ring:
                        if len(pt) >= 2:
                            pt[0] = round(pt[0], 4)
                            pt[1] = round(pt[1], 4)
    return fc


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "wri_aqueduct_baseline_annual.geojson"

    print(f"Fetching WRI Aqueduct Baseline Annual from {FEATURE_SERVICE}")

    count_resp = requests.get(
        FEATURE_SERVICE,
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        timeout=30,
    )
    count_resp.raise_for_status()
    total = count_resp.json().get("count", 0)
    print(f"Total features: {total}")

    all_features: list[dict] = []
    offset = 0
    while offset < total:
        print(f"  fetching offset={offset}...", end=" ", flush=True)
        try:
            fc = fetch_page(offset)
        except requests.RequestException as e:
            print(f"ERROR: {e}")
            time.sleep(2)
            continue
        features = fc.get("features", [])
        print(f"got {len(features)} features")
        all_features.extend(features)
        offset += MAX_RECORDS
        time.sleep(DELAY)

    print(f"Total fetched: {len(all_features)}")
    if not all_features:
        print("No data fetched, aborting.")
        return 1

    merged: dict = {
        "type": "FeatureCollection",
        "features": all_features,
        "metadata": {
            "source": "WRI Aqueduct 4.0",
            "license": "CC BY 4.0",
            "description": "Baseline Annual water risk indicators (1979-2019)",
            "attribute_fields": OUT_FIELDS,
        },
    }

    merged = simplify_geojson(merged)
    text = json.dumps(merged, ensure_ascii=False)
    raw_bytes = text.encode("utf-8")
    compressed = zlib.compress(raw_bytes, level=6)
    print(f"GeoJSON: {len(raw_bytes) / 1024 / 1024:.1f} MB raw, {len(compressed) / 1024 / 1024:.1f} MB compressed")

    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
