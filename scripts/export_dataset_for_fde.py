"""Export selected Atlas source datasets into CSV files for FDE upload."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "fde"
DATA_CENTER_SOURCE = PROJECT_ROOT / "config" / "datacenter_locations.yaml"


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


def export_dataset(dataset: str, output: Path | None = None) -> Path:
    if dataset != "data_centers":
        raise ValueError("Supported datasets: data_centers")

    rows = _data_center_rows()
    if not rows:
        raise ValueError("No rows found for data_centers")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output or EXPORT_DIR / "data_centers.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an Atlas dataset to CSV for Future Dataset Engine upload.")
    parser.add_argument("--dataset", default="data_centers", choices=["data_centers"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    output_path = export_dataset(args.dataset, args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
