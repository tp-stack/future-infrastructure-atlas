"""Generate atlas_core.json — small metadata-only file for the frontend.

Contains counts, sources, disclaimers, tile URLs, license warnings.
No heavy coordinate arrays.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
TILES_DIR = PROJECT_ROOT / "frontend" / "public" / "tiles"
ARTIFACT_TILES_DIR = PROJECT_ROOT / "data" / "tiles"
LEGACY_POWER_CACHE = PROJECT_ROOT / "scripts" / "data" / "cache"
POWER_CACHE = PROJECT_ROOT / "data" / "cache" / "pypsa_eur"
DEFAULT_MAX_LOCAL_PMTILES_MB = 100.0
POWER_LINES_REMOTE_ENV = "POWER_LINES_PMTILES_URL"
POWER_LINES_REMOTE_WARNING = (
    "Power-line PMTiles require remote object storage for Hobby-safe deploys. "
    "Set POWER_LINES_PMTILES_URL to a public HTTPS PMTiles URL with CORS and Range request support."
)


def _check_tile(name: str) -> str:
    path = TILES_DIR / name
    if path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        return f"present ({size_mb:.2f} MB)"
    artifact_path = ARTIFACT_TILES_DIR / name
    if artifact_path.exists():
        size_mb = artifact_path.stat().st_size / (1024 * 1024)
        return f"artifact_only ({size_mb:.2f} MB in data/tiles; not publicly served)"
    return "missing"


def _file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def _max_local_pmtiles_mb() -> float:
    raw = os.environ.get("MAX_LOCAL_PMTILES_MB")
    if not raw:
        return DEFAULT_MAX_LOCAL_PMTILES_MB
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_MAX_LOCAL_PMTILES_MB


def _local_tile_entry(key: str, filename: str) -> dict:
    return {
        "url": f"/tiles/{filename}",
        "status": _check_tile(filename),
        "layer_name": key,
    }


def _power_lines_tile_entry(max_local_mb: float) -> tuple[dict, dict | None]:
    remote_url = os.environ.get(POWER_LINES_REMOTE_ENV, "").strip()
    local_path = TILES_DIR / "power_lines.pmtiles"
    artifact_path = ARTIFACT_TILES_DIR / "power_lines.pmtiles"

    if remote_url:
        if remote_url.startswith("https://"):
            return (
                {
                    "url": f"pmtiles://{remote_url}",
                    "status": "present (remote)",
                    "layer_name": "power_lines",
                    "deployment_mode": "remote",
                },
                None,
            )
        return (
            {
                "url": "",
                "status": f"missing (invalid {POWER_LINES_REMOTE_ENV}; must start with https://)",
                "layer_name": "power_lines",
                "deployment_mode": "invalid_remote",
            },
            {
                "layer": "power_lines",
                "message": f"{POWER_LINES_REMOTE_ENV} must start with https://.",
                "active": True,
            },
        )

    if local_path.exists():
        size_mb = _file_size_mb(local_path)
        if size_mb <= max_local_mb:
            return (
                {
                    "url": "pmtiles:///tiles/power_lines.pmtiles",
                    "status": f"present ({size_mb:.2f} MB)",
                    "layer_name": "power_lines",
                    "deployment_mode": "local",
                },
                None,
            )
        return (
            {
                "url": "",
                "status": f"remote_required ({size_mb:.2f} MB local file exceeds {max_local_mb:.0f} MB deploy threshold)",
                "layer_name": "power_lines",
                "deployment_mode": "remote_required",
            },
            {
                "layer": "power_lines",
                "message": POWER_LINES_REMOTE_WARNING,
                "active": True,
            },
        )

    if artifact_path.exists():
        size_mb = _file_size_mb(artifact_path)
        return (
            {
                "url": "",
                "status": f"remote_required ({size_mb:.2f} MB artifact in data/tiles; not publicly served)",
                "layer_name": "power_lines",
                "deployment_mode": "remote_required",
            },
            {
                "layer": "power_lines",
                "message": POWER_LINES_REMOTE_WARNING,
                "active": True,
            },
        )

    return (
        {
            "url": "",
            "status": "missing",
            "layer_name": "power_lines",
            "deployment_mode": "missing",
        },
        {
            "layer": "power_lines",
            "message": "power_lines.pmtiles is missing. Build it or set POWER_LINES_PMTILES_URL.",
            "active": True,
        },
    )


def _merge_sources(sources: list[dict], extra_sources: list[dict]) -> list[dict]:
    merged = list(sources)
    seen = {str(s.get("key") or s.get("name")) for s in merged if isinstance(s, dict)}
    for source in extra_sources:
        key = str(source.get("key") or source.get("name"))
        if key not in seen:
            merged.append(source)
            seen.add(key)
    return merged


def _count_geojson_features(name: str) -> int:
    path = FRONTEND_DATA / name
    if not path.exists():
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
        return len(features) if isinstance(features, list) else 0
    except (OSError, json.JSONDecodeError):
        return 0


def _geojson_metadata(name: str) -> dict:
    path = FRONTEND_DATA / name
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        metadata = data.get("metadata", {})
        return metadata if isinstance(metadata, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _count_geojson_features_or_metadata(name: str) -> int:
    metadata = _geojson_metadata(name)
    total = metadata.get("total_features")
    if isinstance(total, int):
        return total
    try:
        if total is not None:
            return int(total)
    except (TypeError, ValueError):
        pass
    return _count_geojson_features(name)


def _count_csv_rows(*paths: Path) -> int:
    for path in paths:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return max(sum(1 for _line in f) - 1, 0)
    return 0


def build_atlas_core(data: dict) -> dict:
    counts = data.get("metadata", {}).get("counts", {})
    sources = data.get("metadata", {}).get("sources", [])
    disclaimer = data.get("metadata", {}).get("disclaimer", "")
    power_lines_metadata = _geojson_metadata("power_lines.json")
    power_lines_count = _count_geojson_features_or_metadata("power_lines.json")
    substations_count = _count_geojson_features_or_metadata("substations.json") or _count_csv_rows(
        POWER_CACHE / "buses.csv",
        LEGACY_POWER_CACHE / "buses.csv",
    )
    power_grid_source = power_lines_metadata.get("source") or "PyPSA-Eur v0.7"
    power_grid_source_url = power_lines_metadata.get("source_url") or "https://www.arcgis.com/home/item.html?id=7ba3a1052a324e8c9383481afa9c1fce"
    power_grid_license = power_lines_metadata.get("license") or "ODbL 1.0"
    max_local_pmtiles_mb = _max_local_pmtiles_mb()
    power_lines_tile, power_lines_setup_warning = _power_lines_tile_entry(max_local_pmtiles_mb)
    setup_warnings = [power_lines_setup_warning] if power_lines_setup_warning else []
    sources = _merge_sources(
        sources,
        [
            {
                "key": "osm_europe_power_lines",
                "name": power_grid_source,
                "url": power_grid_source_url,
                "license": power_grid_license,
            }
        ],
    )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "architecture": "atlas_core + PMTiles",
        "counts": {
            "power_plants_total": counts.get("power_plants_total"),
            "power_plants_mapped": counts.get("power_plants_mapped"),
            "power_plants_rejected": counts.get("power_plants_rejected"),
            "submarine_cables_total": counts.get("submarine_cables_total") or counts.get("cables_total"),
            "submarine_cables_mapped": counts.get("submarine_cables_mapped") or counts.get("cables_mapped"),
            "submarine_cables_unmapped": counts.get("submarine_cables_unmapped") or counts.get("cables_unmapped"),
            "data_centers_total": counts.get("data_centers_total"),
            "data_centers_mapped": counts.get("data_centers_mapped"),
            "data_centers_unmapped": counts.get("data_centers_unmapped"),
            "data_center_source": counts.get("data_center_source", ""),
            "data_center_license_status": counts.get("data_center_license_status", ""),
            "cable_geometry_source": counts.get("cable_geometry_source", ""),
            "cable_geometry_license_status": counts.get("cable_geometry_license_status", ""),
            "cable_geometry_review_required": counts.get("cable_geometry_review_required", False),
            "power_lines_total": power_lines_count,
            "power_lines_mapped": power_lines_count,
            "substations_total": substations_count,
            "substations_mapped": substations_count,
            "power_grid_source": power_grid_source,
            "power_grid_license_status": power_grid_license,
        },
        "sources": sources,
        "disclaimer": disclaimer,
        "tile_registry": {
            "power_plants": _local_tile_entry("power_plants", "power_plants.pmtiles"),
            "submarine_cables": _local_tile_entry("submarine_cables", "submarine_cables.pmtiles"),
            "data_centers": _local_tile_entry("data_centers", "data_centers.pmtiles"),
            "power_lines": power_lines_tile,
            "substations": _local_tile_entry("substations", "substations.pmtiles"),
        },
        "license_warnings": [
            {
                "layer": "submarine_cables",
                "message": "Cable geometry source (KMCD) requires license review before production/commercial use.",
                "active": counts.get("cable_geometry_review_required", False),
            },
            {
                "layer": "data_centers",
                "message": "PeeringDB data center source: verify terms before commercial redistribution.",
                "active": True,
            },
            {
                "layer": "power_grid",
                "message": f"{power_grid_source} is {power_grid_license}; attribution and share-alike obligations apply.",
                "active": power_lines_count > 0 or substations_count > 0,
            },
        ],
        "setup_warnings": setup_warnings,
        "data_gaps": {
            "cables_unmapped": (counts.get("submarine_cables_unmapped") or counts.get("cables_unmapped") or 0),
            "data_centers_unmapped": counts.get("data_centers_unmapped", 0),
            "note": "Unmapped entries have no public geometry or coordinates. No coordinates are inferred.",
        },
        "bounds": {
            "power_lines": power_lines_metadata.get("bounds"),
        },
    }


def main() -> None:
    web_data_path = FRONTEND_DATA / "atlas_web_data.json"
    if not web_data_path.exists():
        print(f"ERROR: {web_data_path} not found. Run build_web_map_data.py first.", file=sys.stderr)
        sys.exit(1)

    with open(web_data_path, encoding="utf-8") as f:
        data = json.load(f)

    core = build_atlas_core(data)

    output_path = FRONTEND_DATA / "atlas_core.json"
    raw = json.dumps(core, ensure_ascii=False, indent=2)
    output_path.write_text(raw, encoding="utf-8")

    size_kb = len(raw.encode("utf-8")) / 1024
    print(f"atlas_core.json written to {output_path} ({size_kb:.1f} KB)")
    print(f"  Tile status: power_plants={core['tile_registry']['power_plants']['status']}")
    print(f"  Tile status: submarine_cables={core['tile_registry']['submarine_cables']['status']}")
    print(f"  Tile status: data_centers={core['tile_registry']['data_centers']['status']}")
    print(f"  Tile status: power_lines={core['tile_registry']['power_lines']['status']}")
    print(f"  Tile status: substations={core['tile_registry']['substations']['status']}")
    print(f"  Sources: {len(sources := core['sources'])} entries")
    print(f"  License warnings: {sum(1 for w in core['license_warnings'] if w['active'])}")


if __name__ == "__main__":
    main()
