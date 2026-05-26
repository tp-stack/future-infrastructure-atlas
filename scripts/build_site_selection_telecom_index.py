#!/usr/bin/env python3
"""Build a lightweight derived telecom/interconnection index for site selection.

Produces a compact JSON telecom_index.json (<10 MB) with:
  - ixp_proxy_points: PeeringDB facilities with ix_count > 0 (interconnection hubs)
  - facility_points: All PeeringDB facilities with coordinates (telecom density)
  - Compact separators, null fields dropped, lat/lon rounded to 5 decimal places

This is a separate shard from the main infrastructure index to keep each under 10 MB.
"""

import csv
import json
from pathlib import Path
from datetime import datetime, timezone

MAX_TELECOM_INDEX_SIZE_BYTES = 10_000_000


def _round(v: float | None, decimals: int = 5) -> float | None:
    if v is None:
        return None
    return round(v, decimals)


def _drop_nulls(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _parse_int(v: str | None) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def main():
    base_dir = Path(__file__).parent.parent
    peeringdb_csv = base_dir / "data" / "processed" / "global_datacenters_public_peeringdb.csv"
    output_dir = base_dir / "data" / "derived" / "site_selection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "telecom_index.json"

    if not peeringdb_csv.exists():
        print(f"ERROR: PeeringDB CSV not found at {peeringdb_csv}")
        return 1

    print(f"Loading PeeringDB data from: {peeringdb_csv}")

    facility_features = []
    ixp_features = []

    with open(peeringdb_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat = row.get("latitude")
            lon = row.get("longitude")
            if not lat or not lon:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                continue

            ix_count = _parse_int(row.get("ix_count"))
            net_count = _parse_int(row.get("net_count"))
            facility_type = row.get("facility_type") or None

            feat = _drop_nulls({
                "id": row.get("source_id"),
                "lat": _round(lat_f),
                "lon": _round(lon_f),
                "t": "fac",
                "q": "obs",
                "c": row.get("country"),
                "city": row.get("city"),
                "name": row.get("name"),
                "op": row.get("operator"),
                "ix": ix_count,
                "net": net_count,
            })
            facility_features.append(feat)

            # IXP proxy: facilities connected to one or more IXPs
            if ix_count is not None and ix_count > 0:
                ixp_feat = _drop_nulls({
                    "id": row.get("source_id"),
                    "lat": _round(lat_f),
                    "lon": _round(lon_f),
                    "t": "ixp",
                    "q": "obs",
                    "c": row.get("country"),
                    "city": row.get("city"),
                    "name": row.get("name"),
                    "ix": ix_count,
                })
                ixp_features.append(ixp_feat)

    print(f"Facility points: {len(facility_features)}")
    print(f"IXP proxy points: {len(ixp_features)}")

    generated_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "generated_at": generated_at,
        "source_files": ["data/processed/global_datacenters_public_peeringdb.csv"],
        "source_notes": {
            "facility_points": (
                f"PeeringDB facilities with coordinates. "
                f"{len(facility_features)} points extracted. "
                f"Observed coordinates. Represents telecom facility density."
            ),
            "ixp_proxy_points": (
                f"PeeringDB facilities with ix_count > 0. "
                f"{len(ixp_features)} points extracted. "
                f"Observed coordinates. Proxy for interconnection hub density."
            ),
        },
        "feature_counts": {
            "facility_points": len(facility_features),
            "ixp_proxy_points": len(ixp_features),
        },
        "disclaimer": (
            "These are facility and IXP proximity proxy points from PeeringDB. "
            "Facility proximity does not confirm carrier service, dark fiber availability, "
            "route diversity, or commercial interconnection availability. "
            "IXP proxy points indicate facilities connected to one or more Internet Exchange Points."
        ),
    }

    index = {
        "metadata": metadata,
        "features": {
            "facility_points": facility_features,
            "ixp_proxy_points": ixp_features,
        },
    }

    raw = json.dumps(index, separators=(",", ":"), ensure_ascii=False)
    size = len(raw.encode("utf-8"))
    print(f"Telecom index size: {size} bytes ({size/1024/1024:.1f} MB)")

    if size > MAX_TELECOM_INDEX_SIZE_BYTES:
        print(f"ERROR: Telecom index {size} exceeds {MAX_TELECOM_INDEX_SIZE_BYTES} limit")
        return 1

    with open(output_path, "wb") as f:
        f.write(raw.encode("utf-8"))
    print(f"Telecom index written to: {output_path}")

    # Write human-readable summary
    summary_path = output_dir / "telecom_index_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Telecom Interconnection Index Summary\n")
        f.write(f"Generated at: {generated_at}\n")
        f.write(f"Final size: {size} bytes ({size/1024/1024:.1f} MB)\n")
        f.write(f"Feature counts:\n")
        f.write(f"  facility_points: {len(facility_features)}\n")
        f.write(f"  ixp_proxy_points: {len(ixp_features)}\n")
        f.write(f"Total: {len(facility_features) + len(ixp_features)}\n")

    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())