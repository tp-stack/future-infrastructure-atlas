from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
PROCESSED_WEB = PROJECT_ROOT / "data" / "processed" / "web"

WRI_CSV = PROJECT_ROOT / "data" / "raw" / "wri_global_power_plants" / "manual_20260511" / "global_power_plant_database_wri_all.csv"
CABLES_CSV = PROJECT_ROOT / "data" / "raw" / "submarine_cable_lines" / "manual_20260511" / "global_submarine_cable_lines_scn_segments.csv"
DATACENTERS_CSV = PROJECT_ROOT / "data" / "raw" / "data_centers" / "manual_20260511" / "frontier_ai_data_centers_epoch_public.csv"

VALID_FUELS = {
    "hydro", "solar", "wind", "nuclear", "coal", "natural gas",
    "oil", "biomass", "geothermal", "waste", "cogeneration",
    "wave and tidal", "petroleum", "gas", "other",
}

FUEL_NORMALIZE = {
    "natural gas": "Natural Gas",
    "natural gas with ccs": "Natural Gas",
    "natural gas with carbon capture": "Natural Gas",
    "gas": "Natural Gas",
    "hydro": "Hydro",
    "solar": "Solar",
    "solar pv": "Solar",
    "solar thermal": "Solar",
    "wind": "Wind",
    "wind onshore": "Wind",
    "wind offshore": "Wind",
    "nuclear": "Nuclear",
    "coal": "Coal",
    "oil": "Oil",
    "biomass": "Biomass",
    "geothermal": "Geothermal",
    "waste": "Waste",
    "cogeneration": "Cogeneration",
    "wave and tidal": "Wave and Tidal",
    "petroleum": "Oil",
    "other": "Other",
}


def _find_country_col(fieldnames: list[str]) -> str:
    for f in fieldnames:
        if f.strip().lower() == "country":
            return f
    for f in fieldnames:
        if "country" in f.lower() and "long" not in f.lower():
            return f
    return fieldnames[0]


def _valid_lat(lat_str: str) -> bool:
    try:
        v = float(lat_str)
        return -90 <= v <= 90
    except (ValueError, TypeError):
        return False


def _valid_lng(lng_str: str) -> bool:
    try:
        v = float(lng_str)
        return -180 <= v <= 180
    except (ValueError, TypeError):
        return False


def _normalize_fuel(fuel: str) -> str:
    val = (fuel or "").strip()
    if not val:
        return "Other"
    key = val.lower()
    return FUEL_NORMALIZE.get(key, val)


def _read_wri(path: Path) -> tuple[list[dict], int]:
    records = []
    rejected = 0
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        country_col = _find_country_col(reader.fieldnames)

        for row in reader:
            lat_str = (row.get("latitude") or "").strip()
            lng_str = (row.get("longitude") or "").strip()
            name = (row.get("name") or "").strip()
            fuel_raw = (row.get("primary_fuel") or "").strip()

            if not name or not _valid_lat(lat_str) or not _valid_lng(lng_str):
                rejected += 1
                continue

            country_code = (row.get(country_col) or "").strip()
            country_long = (row.get("country_long") or "").strip()
            display_country = country_long or country_code

            cap_str = (row.get("capacity_mw") or "").strip()
            try:
                mw = round(float(cap_str), 2) if cap_str else 0.0
            except ValueError:
                mw = 0.0

            records.append({
                "n": name,
                "c": display_country,
                "f": _normalize_fuel(fuel_raw),
                "mw": mw,
                "lat": round(float(lat_str), 6),
                "lon": round(float(lng_str), 6),
            })

    return records, rejected


def _read_cables(path: Path) -> tuple[list[dict], int]:
    records = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("cable_system_name") or "").strip()
            if not name:
                continue
            records.append({
                "n": name,
                "operators": (row.get("operators") or "").strip(),
                "landing_points": (row.get("landing_points") or "").strip(),
                "segment_endpoints": (row.get("segment_endpoints") or "").strip(),
                "length_km": (row.get("segment_length_km_raw") or "").strip(),
                "source": (row.get("source_dataset") or "").strip(),
            })
    return records, 0


def _read_datacenters(path: Path) -> tuple[list[dict], int]:
    records = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            power_str = (row.get("current_power_mw") or "").strip()
            try:
                mw = round(float(power_str), 1) if power_str else None
            except ValueError:
                mw = None
            records.append({
                "n": name,
                "op": (row.get("owner") or "").strip(),
                "c": (row.get("country") or "").strip(),
                "address": (row.get("address") or "").strip(),
                "mw": mw,
                "source": (row.get("source_dataset") or "").strip(),
            })
    return records, 0


def build_web_data(max_public_mb: int = 5) -> None:
    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)
    PROCESSED_WEB.mkdir(parents=True, exist_ok=True)

    sources = [
        {
            "key": "wri_global_power_plant_database",
            "name": "WRI Global Power Plant Database",
            "url": "https://datasets.wri.org/dataset/globalpowerplantdatabase",
            "license": "Creative Commons Attribution 4.0 (CC BY 4.0)",
        },
        {
            "key": "scn_submarine_cables",
            "name": "SCN Submarine Cable Network Data",
            "url": "https://github.com/miaw-net/scn-data",
            "license": "Public research dataset",
        },
        {
            "key": "epoch_ai_data_centers",
            "name": "Epoch AI Frontier Data Centers",
            "url": "https://epoch.ai/data/data-centers",
            "license": "Creative Commons Attribution (CC BY)",
        },
    ]

    pp, pp_rej = _read_wri(WRI_CSV)
    cables, _ = _read_cables(CABLES_CSV)
    dcs, _ = _read_datacenters(DATACENTERS_CSV)

    data = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sources": sources,
            "disclaimer": (
                "This map displays infrastructure data from multiple public sources. "
                "Data may be incomplete, outdated, or approximate. "
                "Submarine cable routes are schematic and do not represent actual physical paths. "
                "Data center locations are approximate and may not reflect exact facility coordinates. "
                "Power plant locations are based on public registries and may contain inaccuracies. "
                "This map is for informational purposes only. "
                "See source documentation for detailed methodology and limitations."
            ),
            "counts": {
                "power_plants_mapped": len(pp),
                "power_plants_rejected": pp_rej,
                "submarine_cables_total": len(cables),
                "submarine_cables_mapped": 0,
                "submarine_cables_unmapped": len(cables),
                "data_centers_total": len(dcs),
                "data_centers_mapped": 0,
                "data_centers_unmapped": len(dcs),
            },
            "unmapped": {
                "submarine_cables": [
                    {
                        "n": r["n"],
                        "source": r["source"],
                        "operators": r["operators"],
                        "landing_points": r["landing_points"],
                        "length_km": r["length_km"],
                    }
                    for r in cables
                ],
                "data_centers": [
                    {
                        "n": r["n"],
                        "op": r["op"],
                        "c": r["c"],
                        "address": r["address"],
                        "mw": r["mw"],
                        "source": r["source"],
                    }
                    for r in dcs
                ],
            },
        },
        "power_plants": pp,
        "cables": [],
        "data_centers": [],
    }

    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    size_mb = len(raw.encode("utf-8")) / (1024 * 1024)

    if size_mb <= max_public_mb:
        output_path = FRONTEND_DATA / "atlas_web_data.json"
        output_path.write_text(raw, encoding="utf-8")
        print(f"atlas_web_data.json written to {output_path} ({size_mb:.2f} MB)")
        return True
    else:
        output_path = PROCESSED_WEB / "atlas_web_data.json"
        output_path.write_text(raw, encoding="utf-8")
        print(
            f"ERROR: atlas_web_data.json is {size_mb:.2f} MB, exceeds {max_public_mb} MB limit.",
            file=sys.stderr,
        )
        print(f"Written to {output_path} instead of frontend/public/data/", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact web map data from raw CSVs")
    parser.add_argument(
        "--max-public-mb",
        type=float,
        default=5.0,
        help="Maximum size in MB for frontend public data (default: 5.0)",
    )
    args = parser.parse_args()
    success = build_web_data(max_public_mb=args.max_public_mb)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
