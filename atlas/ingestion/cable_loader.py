"""Load submarine cable geometry from geospatial source files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas.ingestion.geojson_loader import load_geojson_features, normalize_features
from atlas.ingestion.geometry_utils import safe_slug_key


def load_cables_from_geojson(
    path: Path,
    source_name: str = "",
    geometry_precision: str = "generalized_public_geometry",
    source_license: str = "",
    confidence: float = 0.0,
) -> list[dict]:
    if not path.exists():
        return []
    features = load_geojson_features(path)
    normalized = normalize_features(features, expected_geom="LineString")

    cables = []
    seen_names: set[str] = set()
    for nf in normalized:
        props = nf["properties"]
        name = _get_cable_name(props)
        if not name:
            continue
        key = safe_slug_key(name)
        if key in seen_names:
            continue
        seen_names.add(key)

        cables.append({
            "n": name,
            "source": source_name or props.get("source", "") or props.get("source_dataset", "") or "",
            "geometry": nf["coordinates"],
            "geometry_precision": geometry_precision,
            "mapped_status": "mapped",
            "source_license": source_license,
            "confidence": confidence,
        })
    return cables


def _get_cable_name(props: dict) -> str:
    for field in ("name", "cable_name", "cable_system_name", "title"):
        val = props.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def has_license_restriction(source_key: str, config: dict | None = None) -> bool:
    if config is None:
        return source_key in (
            "telegeography_licensed_submarine_cables",
            "emodnet_schematic_cables",
        )
    sources = config.get("sources", []) if isinstance(config, dict) else []
    for s in sources:
        if s.get("source_key") == source_key:
            return s.get("requires_license_review", False)
    return False
