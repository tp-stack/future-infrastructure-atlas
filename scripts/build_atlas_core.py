"""Generate atlas_core.json — small metadata-only file for the frontend.

Contains counts, sources, disclaimers, tile URLs, license warnings.
No heavy coordinate arrays.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
TILES_DIR = PROJECT_ROOT / "frontend" / "public" / "tiles"
ARTIFACT_TILES_DIR = PROJECT_ROOT / "data" / "tiles"


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


def build_atlas_core(data: dict) -> dict:
    counts = data.get("metadata", {}).get("counts", {})
    sources = data.get("metadata", {}).get("sources", [])
    disclaimer = data.get("metadata", {}).get("disclaimer", "")

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
        },
        "sources": sources,
        "disclaimer": disclaimer,
        "tile_registry": {
            "power_plants": {
                "url": "/tiles/power_plants.pmtiles",
                "status": _check_tile("power_plants.pmtiles"),
                "layer_name": "power_plants",
            },
            "submarine_cables": {
                "url": "/tiles/submarine_cables.pmtiles",
                "status": _check_tile("submarine_cables.pmtiles"),
                "layer_name": "submarine_cables",
            },
            "data_centers": {
                "url": "/tiles/data_centers.pmtiles",
                "status": _check_tile("data_centers.pmtiles"),
                "layer_name": "data_centers",
            },
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
        ],
        "data_gaps": {
            "cables_unmapped": (counts.get("submarine_cables_unmapped") or counts.get("cables_unmapped") or 0),
            "data_centers_unmapped": counts.get("data_centers_unmapped", 0),
            "note": "Unmapped entries have no public geometry or coordinates. No coordinates are inferred.",
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
    print(f"  Sources: {len(sources := core['sources'])} entries")
    print(f"  License warnings: {sum(1 for w in core['license_warnings'] if w['active'])}")


if __name__ == "__main__":
    main()
