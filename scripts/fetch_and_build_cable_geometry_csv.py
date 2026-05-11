"""Fetch or read KMCD all_cables GeoJSON, validate, produce structured CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_SOURCE_URL = "https://map.kmcd.dev/data/all_cables.json"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data/raw/submarine_cable_geometries/kmcd_manual_20260511"
    / "world_submarine_cable_geometries_kmcd.csv"
)

CSV_COLUMNS = [
    "cable_feature_id",
    "cable_system_id",
    "cable_name",
    "geometry_type",
    "geometry_json",
    "coordinate_count",
    "segment_count",
    "rfs_year",
    "decommission_year",
    "owners",
    "length",
    "landing_points_json",
    "landing_point_count",
    "source_name",
    "source_url",
    "source_license",
    "license_review_required",
    "geometry_precision",
    "confidence",
    "map_policy",
]

SOURCE_NAME = "KMCD Internet Infrastructure Map"
SOURCE_URL = DEFAULT_SOURCE_URL
SOURCE_LICENSE = "to_verify"
LICENSE_REVIEW_REQUIRED = "true"
GEOMETRY_PRECISION = "generalized_public_geometry"
CONFIDENCE = "0.65"
MAP_POLICY = "draw_source_geometry_only"


def _valid_lon(lon: float) -> bool:
    return -180 <= lon <= 180


def _valid_lat(lat: float) -> bool:
    return -90 <= lat <= 90


def _strip_altitude(coord: list) -> list[float]:
    return [float(coord[0]), float(coord[1])]


def _validate_coord(coord: list) -> bool:
    if not isinstance(coord, (list, tuple)) or len(coord) < 2:
        return False
    lon, lat = float(coord[0]), float(coord[1])
    return _valid_lon(lon) and _valid_lat(lat)


def _validate_line(line: list) -> bool:
    if not line or len(line) < 2:
        return False
    return all(_validate_coord(c) for c in line)


def _normalize_geometry(feature: dict) -> dict | None:
    geom = feature.get("geometry")
    if not geom or not isinstance(geom, dict):
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])

    if gtype == "LineString":
        if not _validate_line(coords):
            return None
        cleaned = [_strip_altitude(c) for c in coords]
        return {"type": "LineString", "coordinates": cleaned}

    if gtype == "MultiLineString":
        cleaned_lines = []
        for line in coords:
            if _validate_line(line):
                cleaned_lines.append([_strip_altitude(c) for c in line])
        if len(cleaned_lines) < 1:
            return None
        return {"type": "MultiLineString", "coordinates": cleaned_lines}

    return None


def _count_coordinates(normalized: dict) -> int:
    if normalized["type"] == "LineString":
        return len(normalized["coordinates"])
    count = 0
    for line in normalized["coordinates"]:
        count += len(line)
    return count


def _count_segments(normalized: dict) -> int:
    if normalized["type"] == "LineString":
        return 1
    return len(normalized["coordinates"])


def _get_prop(props: dict, key: str, default=""):
    val = props.get(key)
    if val is None:
        return default
    return str(val)


def _get_landing_points_json(props: dict) -> str:
    lp = props.get("landing_points")
    if lp is None:
        return ""
    if isinstance(lp, list):
        return json.dumps(lp, ensure_ascii=False)
    return str(lp)


def _get_landing_point_count(props: dict) -> int:
    lp = props.get("landing_points")
    if isinstance(lp, list):
        return len(lp)
    return 0


def process_feature(feature: dict) -> dict | None:
    if not isinstance(feature, dict):
        return None
    if feature.get("type") != "Feature":
        return None

    normalized = _normalize_geometry(feature)
    if normalized is None:
        return None

    props = feature.get("properties") or {}

    feature_id = _get_prop(props, "feature_id")
    sys_id = _get_prop(props, "id")
    name = _get_prop(props, "name")
    rfs_year = _get_prop(props, "rfs_year")
    decommission_year = _get_prop(props, "decommission_year")
    owners = _get_prop(props, "owners")
    length = _get_prop(props, "length")
    landing_points_json = _get_landing_points_json(props)
    landing_point_count = str(_get_landing_point_count(props))

    coord_count = str(_count_coordinates(normalized))
    segment_count = str(_count_segments(normalized))
    geometry_json = json.dumps(normalized, ensure_ascii=False)

    return {
        "cable_feature_id": feature_id,
        "cable_system_id": sys_id,
        "cable_name": name,
        "geometry_type": normalized["type"],
        "geometry_json": geometry_json,
        "coordinate_count": coord_count,
        "segment_count": segment_count,
        "rfs_year": rfs_year,
        "decommission_year": decommission_year,
        "owners": owners,
        "length": length,
        "landing_points_json": landing_points_json,
        "landing_point_count": landing_point_count,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "source_license": SOURCE_LICENSE,
        "license_review_required": LICENSE_REVIEW_REQUIRED,
        "geometry_precision": GEOMETRY_PRECISION,
        "confidence": CONFIDENCE,
        "map_policy": MAP_POLICY,
    }


def load_geojson(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        features = raw.get("features") or raw.get("geometries") or []
        if isinstance(features, list):
            return features
    return []


def download_geojson(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "ATLAS/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        features = raw.get("features") or raw.get("geometries") or []
        if isinstance(features, list):
            return features
    return []


def sha256_checksum(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_csv(rows: list[dict], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch/read KMCD all_cables GeoJSON and produce structured CSV",
    )
    parser.add_argument(
        "--input-geojson",
        type=str,
        default=None,
        help="Local path to KMCD all_cables.json (skip download)",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    output_path = Path(args.output_csv)

    if args.input_geojson:
        input_path = Path(args.input_geojson)
        if not input_path.exists():
            print(f"ERROR: Input GeoJSON not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Reading GeoJSON from: {input_path}")
        features = load_geojson(input_path)
    else:
        url = DEFAULT_SOURCE_URL
        print(f"Downloading GeoJSON from: {url}")
        try:
            features = download_geojson(url)
        except Exception as e:
            print(f"ERROR: Download failed: {e}", file=sys.stderr)
            print(file=sys.stderr)
            print("Manual download command:", file=sys.stderr)
            raw_dir = Path("data/raw/submarine_cable_geometries/kmcd_manual_20260511")
            raw_dir.mkdir(parents=True, exist_ok=True)
            print(
                f'  curl.exe -L "{DEFAULT_SOURCE_URL}" -o "{raw_dir / "all_cables.json"}"',
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Loaded {len(features)} features from GeoJSON")

    valid = 0
    invalid = 0
    rows = []

    for feature in features:
        row = process_feature(feature)
        if row:
            valid += 1
            rows.append(row)
        else:
            invalid += 1

    print(f"Valid features: {valid}")
    print(f"Invalid/rejected: {invalid}")

    written = write_csv(rows, output_path)
    print(f"CSV written: {output_path}")
    print(f"CSV rows: {written}")

    checksum = sha256_checksum(output_path)
    print(f"SHA256: {checksum}")

    output_size = output_path.stat().st_size
    print(f"CSV size: {output_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
