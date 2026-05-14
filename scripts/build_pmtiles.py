"""Generate PMTiles for heavy map layers.

Requires tippecanoe. On Windows, install through WSL or use Docker/Ubuntu.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "pmtiles"
FRONTEND_TILES = PROJECT_ROOT / "frontend" / "public" / "tiles"
DATA_TILES = PROJECT_ROOT / "data" / "tiles"

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
}


def _check_tippecanoe() -> str | None:
    tippecanoe = shutil.which("tippecanoe")
    if tippecanoe:
        return tippecanoe
    if os.path.exists("/usr/local/bin/tippecanoe"):
        return "/usr/local/bin/tippecanoe"
    return None


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


def _run_tippecanoe(
    tippecanoe: str,
    input_path: Path,
    output_path: Path,
    layer_name: str,
    description: str,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        tippecanoe,
        "--output", str(output_path),
        "--layer", layer_name,
        "--name", layer_name,
        "--description", description,
        "--attribution", "Future Infrastructure Atlas",
        "--minimum-zoom", "0",
        "--maximum-zoom", "12",
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--no-tile-compression",
        "--force",
        str(input_path),
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  tippecanoe failed (exit {result.returncode}):", file=sys.stderr)
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                print(f"    {line}", file=sys.stderr)
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
    output_frontend = FRONTEND_TILES / output_name
    output_data = DATA_TILES / output_name

    tippecanoe = _check_tippecanoe()
    if not tippecanoe:
        print(
            "ERROR: Tippecanoe is required to build PMTiles. "
            "On Windows, install through WSL or use Docker/Ubuntu. Do not continue.",
            file=sys.stderr,
        )
        return False

    # Generate NDJSON
    generators = {
        "power_plants": _generate_power_plants_ndjson,
        "submarine_cables": _generate_cables_ndjson,
        "data_centers": _generate_datacenters_ndjson,
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
    print(f"[pmtiles] Generated {count} features for '{layer_key}' → {input_path}")

    # Run tippecanoe
    success = _run_tippecanoe(tippecanoe, input_path, output_frontend, cfg["layer_name"], cfg["description"])
    if not success:
        return False

    # Check size
    size = output_frontend.stat().st_size
    max_bytes = int(max_public_mb * 1024 * 1024)
    if size > max_bytes:
        print(f"  WARNING: {output_name} is {size/1024/1024:.2f} MB > {max_public_mb} MB limit", file=sys.stderr)
        DATA_TILES.mkdir(parents=True, exist_ok=True)
        shutil.move(str(output_frontend), str(output_data))
        print(
            f"  Moved to {output_data}. Use object storage (Cloudflare R2/S3/Vercel Blob) and update tile URLs.",
            file=sys.stderr,
        )
        return False

    # Clean up NDJSON
    input_path.unlink(missing_ok=True)
    print(f"[pmtiles] '{layer_key}' PMTiles ready: {output_frontend} ({size/1024/1024:.2f} MB)")
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
    parser.add_argument("--layer", type=str, default=None, help="Layer to build: power_plants, submarine_cables, data_centers")
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
