"""Aggregate WRI Aqueduct water risk to country-level polygons for fast frontend overlay.

Outputs a small GeoJSON suitable for direct browser use (~200 features).
Also generates NDJSON for PMTiles build when tippecanoe is available.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
PMTILES_DIR = CACHE_DIR / "pmtiles"

# Simplified country boundaries (simplified from Natural Earth)
# We'll compute average water risk per country from the watershed data
COUNTRY_LOOKUP: dict[str, str] = {}


def main() -> int:
    src = CACHE_DIR / "wri_aqueduct_baseline_annual.geojson"
    fc = json.loads(src.read_text(encoding="utf-8"))

    # Aggregate by country (name_0) - compute count, avg overall water risk score
    country_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "wr_sum": 0.0, "bws_sum": 0.0, "bwd_sum": 0.0})

    # Category to numeric score mapping
    cat_score = {
        "Low": 1, "Low-Medium": 2, "Medium-High": 3, "High": 4, "Extremely High": 5,
        "Low - Medium": 2, "Medium high": 3,
    }

    for feat in fc["features"]:
        props = feat.get("properties", {})
        country = (props.get("name_0") or "").strip()
        if not country:
            continue
        st = country_stats[country]
        st["count"] += 1
        wr_raw = props.get("w_awr_def_tot_cat") or ""
        st["wr_sum"] += cat_score.get(wr_raw, 0)
        bws_raw = props.get("bws_cat") or ""
        st["bws_sum"] += cat_score.get(bws_raw, 0)
        bwd_raw = props.get("bwd_cat") or ""
        st["bwd_sum"] += cat_score.get(bwd_raw, 0)

    # Write country-level stats JSON
    stats = {}
    for country, st in sorted(country_stats.items()):
        n = st["count"]
        avg_wr = round(st["wr_sum"] / n, 2) if n else 0
        avg_bws = round(st["bws_sum"] / n, 2) if n else 0
        avg_bwd = round(st["bwd_sum"] / n, 2) if n else 0
        cat = "Low"
        if avg_wr > 4:
            cat = "Extremely High"
        elif avg_wr > 3:
            cat = "High"
        elif avg_wr > 2:
            cat = "Medium-High"
        elif avg_wr > 1:
            cat = "Low-Medium"
        stats[country] = {"n": n, "wr_avg": avg_wr, "bws_avg": avg_bws, "bwd_avg": avg_bwd, "cat": cat}

    out_path = CACHE_DIR / "water_risk_by_country.json"
    out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"Country-level stats ({len(stats)} countries): {out_path}")

    # Also write NDJSON for PMTiles build (full watershed data, simplified)
    ndjson_path = PMTILES_DIR / "water_risk.ndjson"
    PMTILES_DIR.mkdir(parents=True, exist_ok=True)

    cat_num = {"Low": 1, "Low-Medium": 2, "Medium-High": 3, "High": 4, "Extremely High": 5, "Low - Medium": 2, "Medium high": 3}

    count = 0
    with open(ndjson_path, "w", encoding="utf-8") as f:
        for feat in fc["features"]:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue
            wr_cat = props.get("w_awr_def_tot_cat") or ""
            wr_score = cat_num.get(wr_cat, 0)
            feat_out = {
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "wr": wr_score,
                    "bws": cat_num.get(props.get("bws_cat") or "", 0),
                    "bwd": cat_num.get(props.get("bwd_cat") or "", 0),
                },
            }
            f.write(json.dumps(feat_out, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1

    print(f"NDJSON for PMTiles: {ndjson_path} ({count} features)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
