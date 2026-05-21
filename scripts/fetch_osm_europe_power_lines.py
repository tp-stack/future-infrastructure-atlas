"""Fetch all-voltage European power lines from an OSM-derived ArcGIS layer.

The ArcGIS Online layer is a public OSM replica for Europe filtered to
power=line, power=minor_line, and power=cable. It is substantially larger than
the PyPSA-Eur high-voltage model, so this script writes streaming NDGeoJSON for
PMTiles and only a small metadata FeatureCollection for the frontend.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "osm_europe_power_lines"
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"

SERVICE_URL = (
    "https://services-eu1.arcgis.com/zci5bUiJ8olAal7N/arcgis/rest/services/"
    "OpenStreetMap_Power_Lines_for_Europe/FeatureServer/0"
)
QUERY_URL = f"{SERVICE_URL}/query"
OUT_FIELDS = "OBJECTID,osm_id,osm_id2,name,power,voltage,cables,frequency,location,tunnel,bridge,ref"


def _request_json(params: dict[str, str | int], retries: int = 4) -> dict[str, Any]:
    url = f"{QUERY_URL}?{urllib.parse.urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except Exception as exc:  # noqa: BLE001 - retry network/API failures
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"ArcGIS query failed after {retries} attempts: {last_error}") from last_error


def fetch_count() -> int:
    data = _request_json({"where": "1=1", "returnCountOnly": "true", "f": "json"})
    return int(data["count"])


def parse_voltage_kv(raw: Any) -> int:
    """Return the highest OSM voltage value in kV.

    OSM voltage values are usually volts (e.g. 110000), but some records use kV
    directly or contain multiple semicolon/slash-separated values.
    """
    if raw is None:
        return 0
    values: list[float] = []
    for match in re.findall(r"\d+(?:[.,]\d+)?", str(raw)):
        try:
            value = float(match.replace(",", "."))
        except ValueError:
            continue
        if value <= 0:
            continue
        values.append(value / 1000 if value >= 1000 else value)
    if not values:
        return 0
    return int(round(max(values)))


def parse_int(raw: Any) -> int:
    if raw is None:
        return 0
    match = re.search(r"\d+", str(raw))
    return int(match.group(0)) if match else 0


def valid_coord(coord: Any) -> bool:
    return (
        isinstance(coord, list)
        and len(coord) >= 2
        and isinstance(coord[0], (int, float))
        and isinstance(coord[1], (int, float))
        and -180 <= coord[0] <= 180
        and -90 <= coord[1] <= 90
    )


def haversine_km(a: list[float], b: list[float]) -> float:
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))


def geometry_length_km(paths: list[list[list[float]]]) -> float:
    total = 0.0
    for path in paths:
        for idx in range(1, len(path)):
            total += haversine_km(path[idx - 1], path[idx])
    return total


def update_bounds(bounds: dict[str, float] | None, paths: list[list[list[float]]]) -> dict[str, float]:
    if bounds is None:
        bounds = {"minLon": 180.0, "minLat": 90.0, "maxLon": -180.0, "maxLat": -90.0}
    for path in paths:
        for lon, lat in path:
            bounds["minLon"] = min(bounds["minLon"], lon)
            bounds["minLat"] = min(bounds["minLat"], lat)
            bounds["maxLon"] = max(bounds["maxLon"], lon)
            bounds["maxLat"] = max(bounds["maxLat"], lat)
    return bounds


def normalize_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    attrs = feature.get("attributes") or {}
    raw_paths = (feature.get("geometry") or {}).get("paths") or []
    paths = [
        [[round(float(c[0]), 7), round(float(c[1]), 7)] for c in path if valid_coord(c)]
        for path in raw_paths
    ]
    paths = [path for path in paths if len(path) >= 2]
    if not paths:
        return None

    voltage = parse_voltage_kv(attrs.get("voltage"))
    power = attrs.get("power") or ""
    frequency = str(attrs.get("frequency") or "").strip()
    line_type = "HVDC" if frequency in {"0", "0.0"} else str(power or "power_line")
    underground = power == "cable" or str(attrs.get("location") or "").lower() in {"underground", "underwater"}
    underground = underground or str(attrs.get("tunnel") or "").lower() in {"yes", "true", "1"}
    object_id = attrs.get("OBJECTID")
    osm_id = attrs.get("osm_id2") or attrs.get("osm_id") or object_id
    name = attrs.get("name") or attrs.get("ref") or f"OSM way {osm_id}"
    cables = parse_int(attrs.get("cables"))

    geometry: dict[str, Any]
    if len(paths) == 1:
        geometry = {"type": "LineString", "coordinates": paths[0]}
    else:
        geometry = {"type": "MultiLineString", "coordinates": paths}

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "kind": "power_line",
            "id": f"osm-{osm_id}",
            "n": name,
            "voltage": voltage,
            "voltage_raw": attrs.get("voltage") or "",
            "circuits": 0,
            "cables": cables,
            "length_km": round(geometry_length_km(paths), 3),
            "underground": underground,
            "country": "",
            "type": line_type,
            "power": power,
            "frequency": frequency,
            "osm_id": str(osm_id),
            "objectid": object_id,
            "source": "OpenStreetMap",
        },
    }


def fetch_page_after(last_oid: int, page_size: int) -> list[dict[str, Any]]:
    data = _request_json(
        {
            "where": f"OBJECTID > {last_oid}",
            "outFields": OUT_FIELDS,
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": page_size,
            "orderByFields": "OBJECTID ASC",
            "f": "json",
        }
    )
    return data.get("features") or []


def fetch_features(
    output_ndjson: Path,
    limit: int | None = None,
    page_size: int = 2000,
    workers: int = 1,
) -> dict[str, Any]:
    total = fetch_count()
    if limit is not None:
        total = min(total, limit)

    output_ndjson.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    total_km = 0.0
    voltage_distribution: Counter[int] = Counter()
    power_distribution: Counter[str] = Counter()
    bounds: dict[str, float] | None = None

    if workers != 1:
        print("  note: using keyset pagination; --workers is ignored for ArcGIS stability")

    last_oid = 0
    with output_ndjson.open("w", encoding="utf-8") as out:
        while count + skipped < total:
            features = fetch_page_after(last_oid, page_size)
            if not features:
                break
            next_last_oid = last_oid
            for raw_feature in features:
                attrs = raw_feature.get("attributes") or {}
                object_id = attrs.get("OBJECTID")
                if isinstance(object_id, int):
                    next_last_oid = max(next_last_oid, object_id)
                feature = normalize_feature(raw_feature)
                if not feature:
                    skipped += 1
                    continue
                out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
                props = feature["properties"]
                voltage_distribution[int(props["voltage"])] += 1
                power_distribution[str(props["power"] or "unknown")] += 1
                total_km += float(props["length_km"])
                geom = feature["geometry"]
                paths = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
                bounds = update_bounds(bounds, paths)
                count += 1
            if next_last_oid <= last_oid:
                raise RuntimeError(f"OBJECTID pagination did not advance beyond {last_oid}")
            last_oid = next_last_oid
            print(f"  fetched through OBJECTID {last_oid:,}; completed {count + skipped:,}/{total:,}; wrote {count:,}", flush=True)

    return {
        "total_features": count,
        "skipped_features": skipped,
        "total_route_km": round(total_km),
        "bounds": bounds,
        "voltage_distribution": dict(sorted(voltage_distribution.items())),
        "power_distribution": dict(sorted(power_distribution.items())),
    }


def write_frontend_metadata(metadata: dict[str, Any], ndjson_path: Path) -> None:
    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)
    rel_ndjson = ndjson_path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    payload = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            **metadata,
            "pmtiles_input": rel_ndjson,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "OpenStreetMap Power Lines for Europe via ArcGIS Online",
            "source_url": SERVICE_URL,
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "scope": "Europe power=line, power=minor_line, and power=cable; all voltage values present in OSM tags.",
            "precision_note": "Frontend GeoJSON intentionally stores metadata only. Full line geometry is served from PMTiles.",
        },
    }
    out_path = FRONTEND_DATA / "power_lines.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path = CACHE_DIR / "metadata.json"
    metadata_path.write_text(json.dumps(payload["metadata"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"metadata: {out_path}")
    print(f"metadata cache: {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch all-voltage OSM Europe power lines for PMTiles")
    parser.add_argument("--limit", type=int, default=None, help="Fetch only N features for testing")
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--workers", type=int, default=8, help="Concurrent ArcGIS page requests")
    args = parser.parse_args()

    if args.page_size < 1 or args.page_size > 2000:
        print("ERROR: --page-size must be between 1 and 2000 for this ArcGIS service", file=sys.stderr)
        sys.exit(2)

    output_ndjson = CACHE_DIR / "power_lines.ndjson"
    print("=== Fetching OSM Europe power lines (all voltages) ===")
    metadata = fetch_features(output_ndjson, limit=args.limit, page_size=args.page_size, workers=args.workers)
    write_frontend_metadata(metadata, output_ndjson)
    print(f"ndjson: {output_ndjson}")
    print(f"features: {metadata['total_features']:,}")
    print(f"route length: {metadata['total_route_km']:,} km")


if __name__ == "__main__":
    main()
