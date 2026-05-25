#!/usr/bin/env python3
"""Build a lightweight derived land suitability index for site selection scoring.

Produces a compact JSON index (<10 MB) with:
  - industrial_proxy_points: centroid proxies derived from power plant clusters
    (observed proxy for industrial/utility zones)
  - Compact separators, null fields dropped, lat/lon rounded to 5 decimal places.
"""

import json
import math
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

MAX_INDEX_SIZE_BYTES = 10_000_000
MIN_POWER_PLANTS_PER_CLUSTER = 2
CLUSTER_CELL_DEG = 0.25


def _round(v: float | None, decimals: int = 5) -> float | None:
    if v is None:
        return None
    return round(v, decimals)


def _drop_nulls(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _grid_cell_key(lat: float, lon: float, cell_deg: float) -> tuple[int, int]:
    return (int(math.floor(lat / cell_deg)), int(math.floor(lon / cell_deg)))


def _build_industrial_proxy_points(
    power_plants: list[dict],
    cell_deg: float = CLUSTER_CELL_DEG,
    min_per_cluster: int = MIN_POWER_PLANTS_PER_CLUSTER,
) -> list[dict]:
    """Build industrial proxy points by clustering power plants by grid cell.

    Each grid cell that contains at least `min_per_cluster` power plants gets one
    centroid proxy point. This is a derived/observed proxy for industrial zones.
    """
    cells: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for pp in power_plants:
        lat = pp.get("lat")
        lon = pp.get("lon")
        if lat is None or lon is None:
            continue
        key = _grid_cell_key(lat, lon, cell_deg)
        cells[key].append(pp)

    proxies: list[dict] = []
    idx = 0
    for key, group in cells.items():
        if len(group) < min_per_cluster:
            continue
        avg_lat = sum(p.get("lat", 0) for p in group) / len(group)
        avg_lon = sum(p.get("lon", 0) for p in group) / len(group)
        avg_mw = sum(p.get("mw", 0) or 0 for p in group) / len(group)
        countries = {p.get("c") for p in group if p.get("c")}

        proxy = _drop_nulls({
            "id": f"ind-{idx}",
            "lat": _round(avg_lat),
            "lon": _round(avg_lon),
            "t": "ind",
            "q": "der",
            "n": len(group),
            "mw": _round(avg_mw, 0),
            "c": ", ".join(sorted(countries)) if len(countries) <= 3 else "multiple",
        })
        proxies.append(proxy)
        idx += 1

    return proxies


def _build_land_index(infra_index_path: Path) -> dict:
    """Build the land suitability index from the infrastructure index."""
    print(f"Reading infrastructure index from {infra_index_path}")
    with open(infra_index_path, "r", encoding="utf-8") as f:
        infra = json.load(f)

    power_plants = infra.get("features", {}).get("power_plant_points", [])
    print(f"  Power plant points available: {len(power_plants)}")

    industrial_proxies = _build_industrial_proxy_points(power_plants)
    print(f"  Industrial proxy points (clustered): {len(industrial_proxies)}")

    features: dict[str, list[dict]] = {
        "industrial_proxy_points": industrial_proxies,
    }

    feature_counts = {}
    for k, v in features.items():
        feature_counts[k] = len(v)

    index = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "description": "Lightweight land suitability index for site selection",
            "feature_counts": feature_counts,
            "source_notes": {
                "industrial_proxy_points": (
                    f"Derived centroid proxies from {len(power_plants)} power plant "
                    f"locations (clustered at {CLUSTER_CELL_DEG}° grid). "
                    f"Proxy for industrial/utility zone proximity — not verified zoning data."
                ),
            },
            "empty_categories_warning": (
                "The following categories have zero features, "
                "meaning land scoring relies on proxy proximity only: "
                "no verified zoning, ownership, or brownfield data."
            ),
        },
        "features": features,
    }

    return index


def main() -> int:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "derived" / "site_selection"
    infra_index_path = data_dir / "infrastructure_index.json"
    output_path = data_dir / "land_index.json"

    if not infra_index_path.exists():
        print(f"ERROR: Infrastructure index not found at {infra_index_path}")
        print("Run build_site_selection_infrastructure_index.py first.")
        return 1

    data_dir.mkdir(parents=True, exist_ok=True)

    index = _build_land_index(infra_index_path)

    json_bytes = json.dumps(index, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    size = len(json_bytes)

    print(f"\nLand index size: {size} bytes ({size/1024/1024:.1f} MB)")
    if size > MAX_INDEX_SIZE_BYTES:
        print(f"ERROR: Land index exceeds max size of {MAX_INDEX_SIZE_BYTES} bytes")
        return 1

    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"Written to {output_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
