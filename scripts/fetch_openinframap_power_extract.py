"""Extract OpenInfraMap-equivalent power data from OpenStreetMap.

OpenInfraMap visualises OpenStreetMap infrastructure. This script does not
scrape OpenInfraMap map tiles; it queries OSM through Overpass for the same
power feature classes in a viewport or bbox, then writes NDJSON inputs that can
be turned into supplemental PMTiles layers.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch_osm_global_power_grid import (
    POWER_LINE_VALUES,
    centroid,
    make_stats,
    normalize_line_feature,
    normalize_substation_feature,
    update_bounds,
)

CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "openinframap_power_extract"
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SOURCE_NAME = "OpenStreetMap power infrastructure via OpenInfraMap-compatible Overpass extract"
SOURCE_URL = "https://openinframap.org/"


def parse_openinframap_url(url: str) -> tuple[float, float, float]:
    match = re.search(r"#(?P<zoom>\d+(?:\.\d+)?)/(?P<lat>-?\d+(?:\.\d+)?)/(?P<lon>-?\d+(?:\.\d+)?)", url)
    if not match:
        raise ValueError("Expected an OpenInfraMap URL like https://openinframap.org/#5.83/46.28/17.082")
    return float(match.group("zoom")), float(match.group("lat")), float(match.group("lon"))


def bbox_from_view(zoom: float, lat: float, lon: float, width: int = 1366, height: int = 768) -> tuple[float, float, float, float]:
    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n
    x0 = x - width / 1024
    x1 = x + width / 1024
    y0 = y - height / 1024
    y1 = y + height / 1024
    min_lon = x0 / n * 360 - 180
    max_lon = x1 / n * 360 - 180
    min_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y1 / n))))
    max_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y0 / n))))
    return min_lat, min_lon, max_lat, max_lon


def overpass_query(bbox: tuple[float, float, float, float], timeout: int) -> str:
    min_lat, min_lon, max_lat, max_lon = bbox
    box = f"{min_lat:.7f},{min_lon:.7f},{max_lat:.7f},{max_lon:.7f}"
    return f"""
[out:json][timeout:{timeout}][maxsize:1073741824];
(
  way["power"~"^(line|minor_line|cable)$"]({box});
  way["power"="substation"]({box});
  node["power"="substation"]({box});
  relation["power"="substation"]({box});
);
out geom;
"""


def fetch_overpass(query: str, endpoint: str) -> dict[str, Any]:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "future-infrastructure-atlas/1.0 OSM power extract",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


def split_bbox(bbox: tuple[float, float, float, float], grid_size: int) -> list[tuple[float, float, float, float]]:
    if grid_size <= 1:
        return [bbox]
    min_lat, min_lon, max_lat, max_lon = bbox
    lat_step = (max_lat - min_lat) / grid_size
    lon_step = (max_lon - min_lon) / grid_size
    chunks: list[tuple[float, float, float, float]] = []
    for row in range(grid_size):
        for col in range(grid_size):
            chunk_min_lat = min_lat + row * lat_step
            chunk_max_lat = max_lat if row == grid_size - 1 else min_lat + (row + 1) * lat_step
            chunk_min_lon = min_lon + col * lon_step
            chunk_max_lon = max_lon if col == grid_size - 1 else min_lon + (col + 1) * lon_step
            chunks.append((chunk_min_lat, chunk_min_lon, chunk_max_lat, chunk_max_lon))
    return chunks


def line_coords(element: dict[str, Any]) -> list[list[float]]:
    coords: list[list[float]] = []
    for point in element.get("geometry") or []:
        lon = point.get("lon")
        lat = point.get("lat")
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            coords.append([float(lon), float(lat)])
    return coords


def write_metadata(stats: dict[str, Any], line_ndjson: Path, substation_ndjson: Path, output: Path, bbox: tuple[float, float, float, float], source_url: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    line_rel = line_ndjson.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    substation_rel = substation_ndjson.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    metadata = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "total_power_lines": stats["power_lines"],
            "total_substations": stats["substations"],
            "total_route_km": round(stats["total_route_km"], 2),
            "line_bounds": stats["line_bounds"],
            "substation_bounds": stats["substation_bounds"],
            "bbox": {
                "minLat": bbox[0],
                "minLon": bbox[1],
                "maxLat": bbox[2],
                "maxLon": bbox[3],
            },
            "line_voltage_distribution": dict(sorted(stats["line_voltage_distribution"].items())),
            "substation_voltage_distribution": dict(sorted(stats["substation_voltage_distribution"].items())),
            "power_distribution": dict(sorted(stats["power_distribution"].items())),
            "power_lines_pmtiles_input": line_rel,
            "substations_pmtiles_input": substation_rel,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": SOURCE_NAME,
            "source_url": source_url,
            "license": "ODbL 1.0",
            "attribution": "(c) OpenStreetMap contributors",
            "precision_note": "OpenInfraMap is a visualisation of OpenStreetMap infrastructure; extracted data here comes from OSM through Overpass.",
        },
    }
    output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _process_elements(
    data: dict[str, Any],
    line_out: Any,
    substation_out: Any,
    region: str,
    stats: dict[str, Any],
    seen_lines: set[str],
    seen_substations: set[str],
    limit: int | None = None,
) -> None:
    for element in data.get("elements") or []:
        if limit is not None and stats["features_written"] >= limit:
            break
        tags = element.get("tags") or {}
        power = tags.get("power") or ""
        osm_type = element.get("type") or ""
        osm_id = element.get("id")
        if osm_id is None:
            continue

        if osm_type == "way" and power in POWER_LINE_VALUES:
            fid = f"osm-way-{osm_id}"
            if fid in seen_lines:
                continue
            feature = normalize_line_feature(f"way-{osm_id}", tags, line_coords(element), region)
            if not feature:
                continue
            line_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
            seen_lines.add(fid)
            props = feature["properties"]
            stats["power_lines"] += 1
            stats["features_written"] += 1
            stats["total_route_km"] += float(props["length_km"] or 0)
            stats["line_voltage_distribution"][props["voltage"]] += 1
            stats["power_distribution"][props["power"] or "unknown"] += 1
            stats["line_bounds"] = update_bounds(stats["line_bounds"], feature["geometry"]["coordinates"] if feature["geometry"]["type"] == "LineString" else [pt for path in feature["geometry"]["coordinates"] for pt in path])
            continue

        if power == "substation":
            fid = f"osm-{osm_type}-{osm_id}"
            if fid in seen_substations:
                continue
            lon: float | None = None
            lat: float | None = None
            if osm_type == "node":
                lon = element.get("lon")
                lat = element.get("lat")
            elif isinstance(element.get("center"), dict):
                lon = element["center"].get("lon")
                lat = element["center"].get("lat")
            else:
                center = centroid(line_coords(element))
                if center:
                    lon, lat = center
            if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
                continue
            feature = normalize_substation_feature(f"{osm_type}-{osm_id}", tags, float(lon), float(lat), region, str(osm_type))
            if not feature:
                continue
            substation_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
            seen_substations.add(fid)
            stats["substations"] += 1
            stats["features_written"] += 1
            stats["substation_voltage_distribution"][feature["properties"]["voltage"]] += 1
            stats["substation_bounds"] = update_bounds(stats["substation_bounds"], [feature["geometry"]["coordinates"]])


def process_elements(data: dict[str, Any], line_ndjson: Path, substation_ndjson: Path, region: str, limit: int | None = None) -> dict[str, Any]:
    stats = make_stats()
    seen_lines: set[str] = set()
    seen_substations: set[str] = set()
    with line_ndjson.open("w", encoding="utf-8") as line_out, substation_ndjson.open("w", encoding="utf-8") as substation_out:
        _process_elements(data, line_out, substation_out, region, stats, seen_lines, seen_substations, limit)
    stats["regions"].append(region)
    return stats


def fetch_and_process_chunks(
    bbox: tuple[float, float, float, float],
    line_ndjson: Path,
    substation_ndjson: Path,
    region: str,
    endpoint: str,
    timeout: int,
    grid_size: int,
    limit: int | None,
    save_json: Path | None,
    request_sleep: float,
    retries: int,
) -> dict[str, Any]:
    stats = make_stats()
    seen_lines: set[str] = set()
    seen_substations: set[str] = set()
    chunks = split_bbox(bbox, grid_size)
    with line_ndjson.open("w", encoding="utf-8") as line_out, substation_ndjson.open("w", encoding="utf-8") as substation_out:
        for idx, chunk in enumerate(chunks, start=1):
            if limit is not None and stats["features_written"] >= limit:
                break
            save_dir = None
            chunk_path = None
            if save_json:
                save_dir = save_json if save_json.suffix == "" else save_json.with_suffix("")
                save_dir.mkdir(parents=True, exist_ok=True)
                chunk_path = save_dir / f"chunk_{idx:03d}.json"
            if chunk_path and chunk_path.exists():
                print(f"Using cached Overpass chunk {idx}/{len(chunks)} {chunk_path}", flush=True)
                data = json.loads(chunk_path.read_text(encoding="utf-8"))
            else:
                query = overpass_query(chunk, timeout)
                print(f"Querying Overpass chunk {idx}/{len(chunks)} bbox={chunk}", flush=True)
                for attempt in range(1, retries + 2):
                    try:
                        data = fetch_overpass(query, endpoint)
                        break
                    except urllib.error.HTTPError as exc:
                        retryable = exc.code in {429, 502, 503, 504}
                        if not retryable or attempt > retries:
                            raise
                        wait_seconds = request_sleep * attempt
                        print(f"  Overpass HTTP {exc.code}; retrying chunk {idx} in {wait_seconds:.0f}s", flush=True)
                        time.sleep(wait_seconds)
                if chunk_path:
                    chunk_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            _process_elements(data, line_out, substation_out, region, stats, seen_lines, seen_substations, limit)
            if request_sleep > 0:
                time.sleep(request_sleep)
    stats["regions"].append(region)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract OpenInfraMap-equivalent OSM power data for a viewport")
    parser.add_argument("--url", default="", help="OpenInfraMap URL with #zoom/lat/lon")
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"))
    parser.add_argument("--viewport-width", type=int, default=1366)
    parser.add_argument("--viewport-height", type=int, default=768)
    parser.add_argument("--overpass-url", default=DEFAULT_OVERPASS_URL)
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--grid-size", type=int, default=1, help="Split the bbox into NxN Overpass requests")
    parser.add_argument("--request-sleep", type=float, default=5.0, help="Seconds to wait between chunked Overpass requests")
    parser.add_argument("--retries", type=int, default=4, help="Retries for retryable Overpass HTTP errors")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--metadata-output", type=Path, default=FRONTEND_DATA / "openinframap_power_extract.json")
    parser.add_argument("--from-json", type=Path, default=None, help="Use a saved Overpass JSON response instead of querying")
    parser.add_argument("--save-json", type=Path, default=None, help="Save the Overpass JSON response to this ignored/cache path")
    args = parser.parse_args()

    if args.bbox:
        bbox = tuple(args.bbox)  # type: ignore[assignment]
        source_url = SOURCE_URL
    elif args.url:
        zoom, lat, lon = parse_openinframap_url(args.url)
        bbox = bbox_from_view(zoom, lat, lon, args.viewport_width, args.viewport_height)
        source_url = args.url
    else:
        raise SystemExit("Provide --url or --bbox")

    cache_dir = args.cache_dir if args.cache_dir.is_absolute() else PROJECT_ROOT / args.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    line_ndjson = cache_dir / "openinframap_power_lines.ndjson"
    substation_ndjson = cache_dir / "openinframap_substations.ndjson"

    save_path = None
    if args.save_json:
        save_path = args.save_json if args.save_json.is_absolute() else PROJECT_ROOT / args.save_json

    if args.from_json:
        data = json.loads(args.from_json.read_text(encoding="utf-8"))
        stats = process_elements(data, line_ndjson, substation_ndjson, "openinframap-view", args.limit)
    else:
        if args.grid_size > 1:
            stats = fetch_and_process_chunks(
                bbox,
                line_ndjson,
                substation_ndjson,
                "openinframap-view",
                args.overpass_url,
                args.timeout,
                args.grid_size,
                args.limit,
                save_path,
                args.request_sleep,
                args.retries,
            )
        else:
            query = overpass_query(bbox, args.timeout)
            print(f"Querying Overpass bbox={bbox}", flush=True)
            try:
                data = fetch_overpass(query, args.overpass_url)
            except urllib.error.HTTPError as exc:
                if exc.code == 504:
                    raise SystemExit("Overpass timed out for this bbox. Retry with --grid-size 4 or higher.") from exc
                raise
            if save_path:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            stats = process_elements(data, line_ndjson, substation_ndjson, "openinframap-view", args.limit)

    output = args.metadata_output if args.metadata_output.is_absolute() else PROJECT_ROOT / args.metadata_output
    write_metadata(stats, line_ndjson, substation_ndjson, output, bbox, source_url)
    print(f"power lines: {stats['power_lines']:,} -> {line_ndjson}")
    print(f"substations: {stats['substations']:,} -> {substation_ndjson}")
    print(f"metadata: {output}")


if __name__ == "__main__":
    main()
