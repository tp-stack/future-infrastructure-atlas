#!/usr/bin/env python3
"""Build a lightweight environmental constraint index for site selection.

Reads processed NDJSON from fetch_osm_protected_areas.py and builds a compact
environmental index with protected-area centroid points. Flood, seismic, and
wildfire categories remain empty pending source data acquisition.

Future enrichment can add (with same pattern):
  - Flood risk zones from Fathom / GAR15 / JRC
  - Water stress scores from WRI Aqueduct
  - Seismic hazard zones from GSHAP
  - Wildfire risk from GFW / Global Fire Atlas
"""

import json
from pathlib import Path
from datetime import datetime, timezone

MAX_INDEX_SIZE_BYTES = 10_000_000

NDJSON_PATH = Path(__file__).resolve().parent.parent / "data" / "cache" / "osm_protected_areas" / "protected_areas.ndjson"


def _load_protected_area_points() -> list[dict]:
    """Load protected area centroid points from NDJSON cache."""
    if not NDJSON_PATH.exists() or NDJSON_PATH.stat().st_size == 0:
        return []
    points: list[dict] = []
    with open(NDJSON_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                feat = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Keep compact keys: id, lat, lon, t='pa', q='obs', name, pcl, region
            points.append({
                "id": feat.get("id", ""),
                "lat": feat.get("lat"),
                "lon": feat.get("lon"),
                "t": "pa",
                "q": "obs",
                "n": feat.get("n", ""),
                "pcl": feat.get("pcl", ""),
                "region": feat.get("region", ""),
            })
    return points


def _build_environmental_index() -> dict:
    """Build the environmental constraint index."""
    protected = _load_protected_area_points()

    print(f"  Protected area points loaded: {len(protected)}")

    features: dict[str, list[dict]] = {
        "protected_area_points": protected,
        "flood_risk_zones": [],
        "seismic_hazard_zones": [],
        "wildfire_risk_zones": [],
    }

    feature_counts = {}
    for k, v in features.items():
        feature_counts[k] = len(v)

    # Build source notes
    pa_note = (
        f"{len(protected)} protected area centroid points from OSM "
        f"boundary=protected_area / leisure=nature_reserve via Geofabrik extracts. "
        f"Source quality: observed. Coverage: regions processed by "
        f"fetch_osm_protected_areas.py."
    ) if protected else (
        "EMPTY — no protected area dataset available. "
        "Run fetch_osm_protected_areas.py to populate from OSM Geofabrik extracts, "
        "or integrate WDPA (protectedplanet.net)."
    )

    index = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "description": (
                "Lightweight environmental constraint index for site selection. "
                "Protected-area points are included if fetch_osm_protected_areas.py "
                "has been run. Flood, seismic, and wildfire categories are empty "
                "pending source data acquisition."
            ),
            "feature_counts": feature_counts,
            "source_notes": {
                "protected_area_points": pa_note,
                "flood_risk_zones": (
                    "EMPTY — no flood risk dataset available. "
                    "Recommended source: JRC Global Flood Hazard Map or Fathom."
                ),
                "seismic_hazard_zones": (
                    "EMPTY — no seismic hazard dataset available. "
                    "Recommended source: GSHAP global hazard map."
                ),
                "wildfire_risk_zones": (
                    "EMPTY — no wildfire risk dataset available. "
                    "Recommended source: Global Fire Emissions Database or GFW."
                ),
            },
            "empty_categories_warning": (
                "Flood, seismic, and wildfire categories are empty. "
                "These exclusion thresholds are currently untriggered. "
                "Environmental due diligence is required for every candidate."
            ),
        },
        "features": features,
    }

    return index


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "derived" / "site_selection"
    output_path = data_dir / "environmental_index.json"

    data_dir.mkdir(parents=True, exist_ok=True)

    index = _build_environmental_index()

    json_bytes = json.dumps(index, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    size = len(json_bytes)

    print(f"Environmental index size: {size} bytes ({size/1024/1024:.1f} MB)")
    if size > MAX_INDEX_SIZE_BYTES:
        print(f"ERROR: Environmental index exceeds max size of {MAX_INDEX_SIZE_BYTES} bytes")
        return 1

    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"Written to {output_path}")

    counts = index["metadata"]["feature_counts"]
    populated = {k: v for k, v in counts.items() if v > 0}
    if populated:
        print(f"  Populated categories: {populated}")
    empty = {k: v for k, v in counts.items() if v == 0}
    if empty:
        print(f"  Empty categories: {list(empty.keys())}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
