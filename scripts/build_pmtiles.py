"""Generate PMTiles for heavy map layers.

Requires tippecanoe. On Windows, install through WSL or use Docker/Ubuntu.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "pmtiles"
FRONTEND_TILES = PROJECT_ROOT / "frontend" / "public" / "tiles"
DATA_TILES = PROJECT_ROOT / "data" / "tiles"
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
LEGACY_POWER_CACHE = PROJECT_ROOT / "scripts" / "data" / "cache"
POWER_CACHE = PROJECT_ROOT / "data" / "cache" / "pypsa_eur"
OSM_POWER_CACHE = PROJECT_ROOT / "data" / "cache" / "osm_europe_power_lines"

MAX_PUBLIC_MB = 25
MAX_PUBLIC_BYTES = MAX_PUBLIC_MB * 1024 * 1024

LAYERS = {
    "power_plants": {
        "input_ndjson": "power_plants.ndjson",
        "output_pmtiles": "power_plants.pmtiles",
        "layer_name": "power_plants",
        "description": "Power plants from WRI Global Power Plant Database",
    },
    "submarine_cables": {
        "input_ndjson": "submarine_cables.ndjson",
        "output_pmtiles": "submarine_cables.pmtiles",
        "layer_name": "submarine_cables",
        "description": "Submarine cable geometries from KMCD Internet Infrastructure Map",
    },
    "data_centers": {
        "input_ndjson": "data_centers.ndjson",
        "output_pmtiles": "data_centers.pmtiles",
        "layer_name": "data_centers",
        "description": "Data center coordinates from PeeringDB",
    },
    "power_lines": {
        "input_ndjson": "power_lines.ndjson",
        "output_pmtiles": "power_lines.pmtiles",
        "layer_name": "power_lines",
        "description": "Global power lines from OpenStreetMap / Geofabrik extracts",
        "maximum_zoom": "10",
    },
    "substations": {
        "input_ndjson": "substations.ndjson",
        "output_pmtiles": "substations.pmtiles",
        "layer_name": "substations",
        "description": "Global substations from OpenStreetMap / Geofabrik extracts",
    },
}


def _check_tippecanoe() -> tuple[str, str] | None:
    tippecanoe = shutil.which("tippecanoe")
    if tippecanoe:
        return ("local", tippecanoe)
    if os.path.exists("/usr/local/bin/tippecanoe"):
        return ("local", "/usr/local/bin/tippecanoe")
    docker = shutil.which("docker")
    if docker:
        return ("docker", docker)
    return None


def _project_relative_container_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise ValueError(f"Path must stay inside project root: {path}") from None
    return f"/work/{rel.as_posix()}"


def _generate_power_plants_ndjson(data: dict, path: Path) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for pp in data.get("power_plants", []):
            lat = pp.get("lat")
            lon = pp.get("lon")
            if lat is None or lon is None:
                continue
            feat = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "n": pp.get("n", ""),
                    "c": pp.get("c", ""),
                    "f": pp.get("f", ""),
                    "mw": pp.get("mw", 0),
                },
            }
            f.write(json.dumps(feat, ensure_ascii=False) + "\n")
            count += 1
    return count


def _generate_cables_ndjson(data: dict, path: Path) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as f:
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
            feat = {
                "type": "Feature",
                "geometry": {"type": gtype, "coordinates": coords},
                "properties": {
                    "n": cable.get("n", ""),
                    "source": cable.get("source", ""),
                    "source_license": cable.get("source_license", ""),
                    "geometry_precision": cable.get("geometry_precision", ""),
                    "confidence": cable.get("confidence", 0),
                },
            }
            f.write(json.dumps(feat, ensure_ascii=False) + "\n")
            count += 1
    return count


def _generate_datacenters_ndjson(data: dict, path: Path) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for dc in data.get("data_centers", []):
            if dc.get("mapped_status") != "mapped":
                continue
            lat = dc.get("lat")
            lon = dc.get("lon")
            if lat is None or lon is None:
                continue
            feat = {
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
            }
            f.write(json.dumps(feat, ensure_ascii=False) + "\n")
            count += 1
    return count


def _valid_coord_pair(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def _load_feature_collection(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _generate_power_lines_ndjson(_data: dict, path: Path) -> int:
    fc = _load_feature_collection(FRONTEND_DATA / "power_lines.json")
    if not fc:
        return 0

    pmtiles_input = (fc.get("metadata") or {}).get("pmtiles_input")
    if pmtiles_input:
        source = PROJECT_ROOT / str(pmtiles_input)
        if not source.exists():
            print(f"ERROR: power_lines pmtiles_input not found: {source}", file=sys.stderr)
            return 0
        shutil.copyfile(source, path)
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for feature in fc.get("features", []):
            geom = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            coords = geom.get("coordinates")
            if geom.get("type") != "LineString" or not isinstance(coords, list) or len(coords) < 2:
                continue
            feat = {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "kind": "power_line",
                    "id": props.get("id", ""),
                    "voltage": props.get("voltage", 0),
                    "circuits": props.get("circuits", 0),
                    "length_km": props.get("length_km", 0),
                    "underground": props.get("underground", False),
                    "country": props.get("country", ""),
                    "type": props.get("type", ""),
                    "s_nom_mva": props.get("s_nom_mva", 0),
                },
            }
            f.write(json.dumps(feat, ensure_ascii=False) + "\n")
            count += 1
    return count


def _find_buses_csv() -> Path | None:
    for candidate in (POWER_CACHE / "buses.csv", LEGACY_POWER_CACHE / "buses.csv"):
        if candidate.exists():
            return candidate
    return None


def _generate_substations_ndjson(_data: dict, path: Path) -> int:
    fc = _load_feature_collection(FRONTEND_DATA / "substations.json")
    if fc:
        pmtiles_input = (fc.get("metadata") or {}).get("pmtiles_input")
        if pmtiles_input:
            source = PROJECT_ROOT / str(pmtiles_input)
            if not source.exists():
                print(f"ERROR: substations pmtiles_input not found: {source}", file=sys.stderr)
                return 0
            shutil.copyfile(source, path)
            with open(path, encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())

    count = 0
    with open(path, "w", encoding="utf-8") as f:
        if fc:
            for feature in fc.get("features", []):
                geom = feature.get("geometry") or {}
                props = feature.get("properties") or {}
                coords = geom.get("coordinates")
                if geom.get("type") != "Point" or not isinstance(coords, list) or len(coords) < 2:
                    continue
                lon = float(coords[0])
                lat = float(coords[1])
                if not _valid_coord_pair(lon, lat):
                    continue
                feat = {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "kind": "substation",
                        "id": props.get("id", ""),
                        "n": props.get("n", props.get("id", "")),
                        "voltage": props.get("voltage", 0),
                        "dc": props.get("dc", False),
                        "symbol": props.get("symbol", ""),
                        "under_construction": props.get("under_construction", False),
                        "country": props.get("country", ""),
                        "lat": lat,
                        "lon": lon,
                    },
                }
                f.write(json.dumps(feat, ensure_ascii=False) + "\n")
                count += 1
            return count

        buses_csv = _find_buses_csv()
        if buses_csv is None:
            return 0
        with open(buses_csv, encoding="utf-8", newline="") as src:
            reader = csv.DictReader(src)
            for row in reader:
                try:
                    lon = float(row.get("x") or "")
                    lat = float(row.get("y") or "")
                except ValueError:
                    continue
                if not _valid_coord_pair(lon, lat):
                    continue
                try:
                    voltage = int(float(row.get("voltage") or 0))
                except ValueError:
                    voltage = 0
                bus_id = row.get("bus_id", "")
                feat = {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "kind": "substation",
                        "id": bus_id,
                        "n": bus_id,
                        "voltage": voltage,
                        "dc": row.get("dc", "") == "t",
                        "symbol": row.get("symbol", ""),
                        "under_construction": row.get("under_construction", "") == "t",
                        "country": row.get("country", ""),
                        "lat": lat,
                        "lon": lon,
                    },
                }
                f.write(json.dumps(feat, ensure_ascii=False) + "\n")
                count += 1
    return count


def _run_tippecanoe(
    tippecanoe_runner: tuple[str, str],
    input_path: Path,
    output_path: Path,
    layer_name: str,
    description: str,
    maximum_zoom: str = "12",
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    runner_kind, runner_cmd = tippecanoe_runner
    tippecanoe = "tippecanoe"
    input_arg = str(input_path)
    output_arg = str(output_path)
    if runner_kind == "local":
        tippecanoe = runner_cmd
    elif runner_kind == "docker":
        input_arg = _project_relative_container_path(input_path)
        output_arg = _project_relative_container_path(output_path)

    cmd = [
        tippecanoe,
        "--output", output_arg,
        "--layer", layer_name,
        "--name", layer_name,
        "--description", description,
        "--attribution", "Future Infrastructure Atlas",
        "--minimum-zoom", "0",
        "--maximum-zoom", maximum_zoom,
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--force",
        input_arg,
    ]
    if runner_kind == "docker":
        inner = " ".join(shlex.quote(part) for part in cmd)
        script = (
            "set -euo pipefail; "
            "export DEBIAN_FRONTEND=noninteractive; "
            "if ! command -v tippecanoe >/dev/null 2>&1; then "
            "apt-get update -qq; "
            "apt-get install -y -qq tippecanoe ca-certificates >/dev/null; "
            "fi; "
            f"{inner}"
        )
        cmd = [
            runner_cmd,
            "run",
            "--rm",
            "-v",
            f"{PROJECT_ROOT}:/work",
            "-w",
            "/work",
            "ubuntu:24.04",
            "bash",
            "-lc",
            script,
        ]

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  tippecanoe failed (exit {result.returncode}):", file=sys.stderr)
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                print(f"    {line}", file=sys.stderr)
        output_path.unlink(missing_ok=True)
        return False
    print(f"  tippecanoe output: {output_path}")
    return True


def build_layer(
    layer_key: str,
    data: dict,
    max_public_mb: float = MAX_PUBLIC_MB,
) -> bool:
    if layer_key not in LAYERS:
        print(f"ERROR: Unknown layer '{layer_key}'. Options: {list(LAYERS.keys())}", file=sys.stderr)
        return False

    cfg = LAYERS[layer_key]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    input_path = CACHE_DIR / cfg["input_ndjson"]
    output_name = cfg["output_pmtiles"]
    output_data = DATA_TILES / output_name
    output_data.parent.mkdir(parents=True, exist_ok=True)

    tippecanoe = _check_tippecanoe()
    if not tippecanoe:
        print(
            "Tippecanoe is required. Use WSL/Ubuntu or Linux to build PMTiles.",
            file=sys.stderr,
        )
        return False

    # Generate NDJSON
    generators = {
        "power_plants": _generate_power_plants_ndjson,
        "submarine_cables": _generate_cables_ndjson,
        "data_centers": _generate_datacenters_ndjson,
        "power_lines": _generate_power_lines_ndjson,
        "substations": _generate_substations_ndjson,
    }
    gen = generators.get(layer_key)
    if not gen:
        print(f"ERROR: No generator for layer '{layer_key}'", file=sys.stderr)
        return False

    count = gen(data, input_path)
    if count == 0:
        print(f"ERROR: No features generated for layer '{layer_key}'", file=sys.stderr)
        input_path.unlink(missing_ok=True)
        return False
    print(f"[pmtiles] Generated {count} features for '{layer_key}' -> {input_path}")

    # Run tippecanoe into ignored artifact storage. PMTiles files are not committed
    # from frontend/public because repository storage safety blocks .pmtiles there.
    success = _run_tippecanoe(
        tippecanoe,
        input_path,
        output_data,
        cfg["layer_name"],
        cfg["description"],
        str(cfg.get("maximum_zoom", "12")),
    )
    if not success:
        return False

    # Check size
    size = output_data.stat().st_size
    max_bytes = int(max_public_mb * 1024 * 1024)
    if size > max_bytes:
        print(f"  WARNING: {output_name} is {size/1024/1024:.2f} MB > {max_public_mb} MB limit", file=sys.stderr)
        print(
            f"  Kept in {output_data}. Use object storage (Cloudflare R2/S3/Vercel Blob) and update tile URLs.",
            file=sys.stderr,
        )
        return False

    # Clean up NDJSON
    input_path.unlink(missing_ok=True)
    print(f"[pmtiles] '{layer_key}' PMTiles artifact ready: {output_data} ({size/1024/1024:.2f} MB)")
    print("  Store externally or copy into a deployment artifact outside git to serve /tiles/*.pmtiles.")
    return True


def load_frontend_data() -> dict | None:
    path = PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_web_data.json"
    if not path.exists():
        print(f"ERROR: Frontend data not found: {path}", file=sys.stderr)
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PMTiles for heavy map layers")
    parser.add_argument("--layer", type=str, default=None, help=f"Layer to build: {', '.join(LAYERS.keys())}")
    parser.add_argument("--all", action="store_true", help="Build all layers")
    parser.add_argument("--max-public-mb", type=float, default=MAX_PUBLIC_MB, help=f"Max MB per PMTiles (default: {MAX_PUBLIC_MB})")
    args = parser.parse_args()

    if not args.all and not args.layer:
        print("ERROR: Specify --layer or --all", file=sys.stderr)
        sys.exit(1)

    if args.layer and args.layer not in LAYERS:
        print(f"ERROR: Unknown layer '{args.layer}'. Options: {list(LAYERS.keys())}", file=sys.stderr)
        sys.exit(1)

    data = load_frontend_data()
    if data is None:
        sys.exit(1)

    layers = list(LAYERS.keys()) if args.all else [args.layer]
    failures = 0
    for lk in layers:
        if not build_layer(lk, data, args.max_public_mb):
            failures += 1

    if failures:
        print(f"\n[pmtiles] {failures} layer(s) failed.", file=sys.stderr)
        sys.exit(1)

    print("\n[pmtiles] All layers built successfully.")


if __name__ == "__main__":
    main()
