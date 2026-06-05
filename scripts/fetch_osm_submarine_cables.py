"""Fetch submarine cables from OpenStreetMap via Overpass API.

OSM submarine cable tagging is deprecated in favor of
  power=cable + location=underwater  (power cables)
  communication=line + location=underwater  (comms cables)

This script queries both the deprecated man_made=submarine_cable tag
and the newer location=underwater approach, then deduplicates.

Output: GeoJSON FeatureCollection with ODbL-licensed geometry.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/raw/submarine_cable_geometries"
    / "osm_submarine_cables.geojson"
)

REGIONS = [
    ("north_atlantic", -50, 25, 10, 65),
    ("europe_med", -10, 30, 30, 60),
    ("asia_pacific", 100, -20, 180, 50),
    ("indian_ocean", 30, -30, 100, 30),
    ("africa_east", 30, -35, 55, 30),
    ("americas_east", -100, -35, -30, 25),
    ("americas_west", -180, -35, -100, 25),
    ("north_pacific", 130, 25, -120, 65),
    ("middle_east", 30, 10, 60, 35),
    ("south_atlantic", -50, -40, 10, 0),
    ("caribbean", -90, 5, -50, 25),
    ("oceania", 140, -50, -160, -10),
]

QUERY_TEMPLATE = """
[out:json][timeout:120];
(
  way["man_made"="submarine_cable"]({south},{west},{north},{east});
  relation["man_made"="submarine_cable"]({south},{west},{north},{east});
  way["location"="underwater"]["power"="cable"]({south},{west},{north},{east});
  relation["location"="underwater"]["power"="cable"]({south},{west},{north},{east});
  way["location"="underwater"]["communication"="line"]({south},{west},{north},{east});
  relation["location"="underwater"]["communication"="line"]({south},{west},{north},{east});
);
out body geom;
>;
out skel geom;
"""


def run_overpass(query: str, region: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={
            "User-Agent": "FUTURE-Infrastructure-Atlas/1.0 (data pipeline; submarine cable extraction)",
        },
    )
    print(f"  [{region}] Querying Overpass ...", flush=True)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - t0
        print(f"  [{region}] {len(result.get('elements', []))} elements in {elapsed:.1f}s")
        return result
    except Exception as e:
        print(f"  [{region}] Failed: {e}", file=sys.stderr)
        return {"elements": []}


def _coord_to_point(coord: dict) -> list[float]:
    return [coord["lon"], coord["lat"]]


def way_to_feature(way: dict) -> dict | None:
    geom_type = way.get("geometry")
    if not geom_type or not isinstance(geom_type, list):
        return None

    coords = []
    for pt in geom_type:
        if isinstance(pt, dict) and "lon" in pt and "lat" in pt:
            coords.append([pt["lon"], pt["lat"]])

    if len(coords) < 2:
        return None

    tags = way.get("tags", {})
    props = {
        "osm_id": str(way["id"]),
        "osm_type": "way",
        "name": tags.get("name", ""),
        "operator": tags.get("operator", ""),
        "ref": tags.get("ref", ""),
        "cables": tags.get("cables", ""),
        "voltage": tags.get("voltage", ""),
        "frequency": tags.get("frequency", ""),
        "rfs_year": tags.get("start_date", ""),
        "location": tags.get("location", ""),
        "source": "OpenStreetMap",
        "source_license": "ODbL",
        "geometry_precision": "osm_public_geometry",
        "confidence": 0.8 if len(coords) > 10 else 0.6,
    }
    props = {k: v for k, v in props.items() if v}

    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": props,
    }


def merge_results(results: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged = []
    for r in results:
        for el in r.get("elements", []):
            if el["type"] == "way":
                feat = way_to_feature(el)
                if feat and feat["properties"]["osm_id"] not in seen:
                    seen.add(feat["properties"]["osm_id"])
                    merged.append(feat)
    return merged


def main() -> None:
    print("Fetching OSM submarine cables by region...")
    all_results = []
    for name, west, south, east, north in REGIONS:
        query = QUERY_TEMPLATE.format(south=south, west=west, north=north, east=east)
        result = run_overpass(query, name)
        all_results.append(result)
        time.sleep(3)

    features = merge_results(all_results)

    # Deduplicate by name where possible
    by_name: dict[str, list[dict]] = {}
    name_count = 0
    for f in features:
        name = f["properties"].get("name", "").lower().strip()
        if name:
            by_name.setdefault(name, []).append(f)
            name_count += 1

    # For cables with same name from different bboxes/overlaps, keep the one with most coords
    deduped = []
    for name, feats in by_name.items():
        feats.sort(key=lambda f: len(f["geometry"]["coordinates"]), reverse=True)
        deduped.append(feats[0])

    unnamed = [f for f in features if not f["properties"].get("name")]
    deduped.extend(unnamed)

    geojson = {"type": "FeatureCollection", "features": deduped}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    print(f"\nWritten: {OUTPUT_PATH}")
    print(f"Features: {len(geojson['features'])}")
    print(f"Named: {name_count}")
    print(f"Unnamed: {len(unnamed)}")

    named_list = sorted(set(f["properties"].get("name", "") for f in deduped if f["properties"].get("name")))
    if named_list:
        print(f"\nUnique named cables ({len(named_list)}):")
        for n in named_list[:40]:
            print(f"  - {n}")
        if len(named_list) > 40:
            print(f"  ... and {len(named_list) - 40} more")


if __name__ == "__main__":
    main()
