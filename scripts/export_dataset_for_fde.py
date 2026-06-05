"""Export selected Atlas source datasets into CSV files for FDE upload."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "fde"
DATA_CENTER_SOURCE = PROJECT_ROOT / "config" / "datacenter_locations.yaml"
ATLAS_WEB_DATA_SOURCE = PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_web_data.json"
POWER_PLANTS_SAMPLE_SIZE = 1000


def _data_center_rows() -> list[dict[str, Any]]:
    data = yaml.safe_load(DATA_CENTER_SOURCE.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {DATA_CENTER_SOURCE}")

    rows = []
    for record_key, values in data.items():
        if not isinstance(values, dict):
            continue
        latitude = values.get("latitude")
        longitude = values.get("longitude")
        rows.append(
            {
                "record_key": record_key,
                "name": values.get("name", ""),
                "latitude": latitude,
                "longitude": longitude,
                "coordinate_precision": values.get("coordinate_precision", ""),
                "coordinate_source": values.get("coordinate_source", ""),
                "source_url": values.get("source_url", ""),
                "source_license": values.get("source_license", ""),
                "confidence": values.get("confidence", ""),
                "notes": values.get("notes", ""),
                "geometry_wkt": f"POINT ({longitude} {latitude})" if latitude is not None and longitude is not None else "",
            }
        )
    return rows


def _slug(value: str, fallback: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    safe = "_".join(part for part in safe.split("_") if part)
    return safe[:80] or fallback


def _data_center_full_rows() -> list[dict[str, Any]]:
    payload = json.loads(ATLAS_WEB_DATA_SOURCE.read_text(encoding="utf-8"))
    data_centers = payload.get("data_centers", [])
    if not isinstance(data_centers, list):
        raise ValueError(f"Expected data_centers list in {ATLAS_WEB_DATA_SOURCE}")

    rows = []
    for index, record in enumerate(data_centers, start=1):
        if not isinstance(record, dict):
            continue
        latitude = record.get("lat")
        longitude = record.get("lon")
        name = record.get("n") or record.get("name") or ""
        rows.append(
            {
                "record_key": f"dc_{index:06d}_{_slug(str(name), 'unnamed')}",
                "name": name,
                "operator": record.get("op", ""),
                "city": record.get("city", ""),
                "region": record.get("region", ""),
                "country": record.get("c", ""),
                "latitude": latitude,
                "longitude": longitude,
                "source": record.get("source", ""),
                "source_url": record.get("source_url", ""),
                "source_license": record.get("source_license", ""),
                "coordinate_precision": record.get("coordinate_precision", ""),
                "coordinate_source": record.get("coordinate_source", ""),
                "confidence": record.get("confidence", ""),
                "mapped_status": record.get("mapped_status", ""),
                "unmapped_reason": record.get("unmapped_reason", ""),
                "capacity_mw": record.get("mw", ""),
                "net_count": record.get("net_count", ""),
                "ix_count": record.get("ix_count", ""),
                "address": record.get("address", ""),
                "geometry_wkt": f"POINT ({longitude} {latitude})" if latitude is not None and longitude is not None else "",
                "raw_metadata_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
            }
        )
    return rows


def _power_plant_sample_rows(limit: int = POWER_PLANTS_SAMPLE_SIZE) -> list[dict[str, Any]]:
    payload = json.loads(ATLAS_WEB_DATA_SOURCE.read_text(encoding="utf-8"))
    power_plants = payload.get("power_plants", [])
    if not isinstance(power_plants, list):
        raise ValueError(f"Expected power_plants list in {ATLAS_WEB_DATA_SOURCE}")

    rows = []
    for index, record in enumerate(power_plants[:limit], start=1):
        if not isinstance(record, dict):
            continue
        latitude = record.get("lat")
        longitude = record.get("lon")
        name = record.get("n") or record.get("name") or ""
        rows.append(
            {
                "record_key": f"pp_{index:06d}_{_slug(str(name), 'unnamed')}",
                "name": name,
                "country": record.get("c", ""),
                "region": record.get("region", ""),
                "latitude": latitude,
                "longitude": longitude,
                "capacity_mw": record.get("mw", ""),
                "fuel": record.get("f", ""),
                "technology": record.get("technology", ""),
                "source": record.get("source", "frontend/public/data/atlas_web_data.json"),
                "source_url": record.get("source_url", ""),
                "mapped_status": record.get("mapped_status", "mapped" if latitude is not None and longitude is not None else "unmapped"),
                "geometry_wkt": f"POINT ({longitude} {latitude})" if latitude is not None and longitude is not None else "",
                "raw_metadata_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
            }
        )
    return rows


def export_dataset(dataset: str, output: Path | None = None) -> Path:
    if dataset == "data_centers":
        rows = _data_center_rows()
        default_name = "data_centers.csv"
    elif dataset == "data_centers_full":
        rows = _data_center_full_rows()
        default_name = "data_centers_full.csv"
    elif dataset == "power_plants_sample":
        rows = _power_plant_sample_rows()
        default_name = "power_plants_sample.csv"
    else:
        raise ValueError("Supported datasets: data_centers, data_centers_full, power_plants_sample")

    if not rows:
        raise ValueError(f"No rows found for {dataset}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output or EXPORT_DIR / default_name
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an Atlas dataset to CSV for Future Dataset Engine upload.")
    parser.add_argument("--dataset", default="data_centers", choices=["data_centers", "data_centers_full", "power_plants_sample"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    output_path = export_dataset(args.dataset, args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
