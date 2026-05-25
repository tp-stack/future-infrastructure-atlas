"""JSONL-based candidate persistence for site selection.

Storage path is configured via SITE_SELECTION_STORAGE_DIR env var,
with fallback to data/reports/site_selection relative to the project root.

In serverless (read-only) environments where the storage path is not writable,
persistence degrades gracefully: candidates are generated but not persisted,
and the candidate detail and export endpoints will return 404 for generated IDs.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlas.site_selection.models import CandidateSite

DISCLAIMER_TEXT = (
    "This system does not provide engineering, legal, permitting, grid-connection, investment, tax, "
    "environmental or regulatory advice. All candidate locations require independent technical, legal, "
    "grid, environmental and permitting due diligence."
)

_STORAGE_PATH: str | None = os.environ.get("SITE_SELECTION_STORAGE_DIR")

if _STORAGE_PATH:
    STORAGE_DIR = Path(_STORAGE_PATH).resolve()
else:
    STORAGE_DIR = Path(__file__).resolve().parents[3] / "data" / "reports" / "site_selection"

_storage_writable: bool | None = None


def _is_storage_writable() -> bool:
    global _storage_writable
    if _storage_writable is not None:
        return _storage_writable
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        probe = STORAGE_DIR / ".write_probe"
        probe.write_text("")
        probe.unlink()
        _storage_writable = True
    except (OSError, PermissionError):
        _storage_writable = False
    return _storage_writable


def _ensure_storage_dir() -> Path:
    if not _is_storage_writable():
        raise RuntimeError(
            f"Candidate storage directory is not writable: {STORAGE_DIR}. "
            "Set SITE_SELECTION_STORAGE_DIR to a writable path or deploy with persistent storage."
        )
    return STORAGE_DIR


def _candidate_to_record(candidate: CandidateSite, query_id: str, area: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "candidate_site_id": candidate.candidate_site_id,
        "rank": candidate.rank,
        "lat": candidate.lat,
        "lon": candidate.lon,
        "country": candidate.country,
        "region": candidate.region,
        "municipality": candidate.municipality,
        "area_ha": candidate.area_ha,
        "compute_profile": candidate.compute_profile,
        "final_score": candidate.final_score,
        "confidence_score": candidate.confidence_score,
        "grid_score": candidate.grid_score,
        "fiber_score": candidate.fiber_score,
        "land_score": candidate.land_score,
        "climate_score": candidate.climate_score,
        "water_score": candidate.water_score,
        "regulatory_score": candidate.regulatory_score,
        "market_score": candidate.market_score,
        "incentive_score": candidate.incentive_score,
        "nearest_substation_km": candidate.nearest_substation_km,
        "nearest_fiber_km": candidate.nearest_fiber_km,
        "nearest_ixp_km": candidate.nearest_ixp_km,
        "estimated_grid_capacity_mw": candidate.estimated_grid_capacity_mw,
        "flood_risk_score": candidate.flood_risk_score,
        "water_stress_score": candidate.water_stress_score,
        "regulatory_stability_score": candidate.regulatory_stability_score,
        "missing_data_flags": candidate.missing_data_flags,
        "human_review_required": candidate.human_review_required,
        "evidence_summary": candidate.evidence_summary,
        "excluded": candidate.excluded,
        "exclusion_reasons": candidate.exclusion_reasons,
        "soft_constraints": candidate.soft_constraints,
        "analysis_area": area,
        "disclaimer": DISCLAIMER_TEXT,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def store_query_batch(candidates: list[CandidateSite], area: dict[str, Any]) -> str:
    query_id = f"q-{uuid.uuid4().hex[:12]}"
    _ensure_storage_dir()
    path = STORAGE_DIR / f"{query_id}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for c in candidates:
            record = _candidate_to_record(c, query_id, area)
            f.write(json.dumps(record, default=str) + "\n")
    return query_id


def load_candidate(candidate_site_id: str) -> dict[str, Any] | None:
    if not _is_storage_writable():
        return None
    if not STORAGE_DIR.exists():
        return None
    for jsonl_path in STORAGE_DIR.glob("*.jsonl"):
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("candidate_site_id") == candidate_site_id:
                    return record
    return None


def load_candidates_by_ids(candidate_ids: list[str]) -> list[dict[str, Any]]:
    if not _is_storage_writable():
        return []
    if not STORAGE_DIR.exists():
        return []
    id_set = set(candidate_ids)
    found: list[dict[str, Any]] = []
    for jsonl_path in STORAGE_DIR.glob("*.jsonl"):
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("candidate_site_id") in id_set:
                    found.append(record)
                    id_set.discard(record.get("candidate_site_id"))
                    if not id_set:
                        return found
    return found


def load_candidates_by_query(query_id: str) -> list[dict[str, Any]]:
    if not _is_storage_writable():
        return []
    path = STORAGE_DIR / f"{query_id}.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def cleanup_old_queries(max_age_days: int | None = None) -> int:
    """Remove JSONL files older than *max_age_days* (default 7).

    Returns the number of files removed.  Uses
    ``SITE_SELECTION_RETENTION_DAYS`` env var when *max_age_days* is *None*.
    Safe to call in serverless (read-only) environments – returns 0.
    """
    if max_age_days is None:
        max_age_days = int(os.environ.get("SITE_SELECTION_RETENTION_DAYS", "7"))
    if not _is_storage_writable():
        return 0
    if not STORAGE_DIR.exists():
        return 0

    cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
    removed = 0
    for jsonl_path in STORAGE_DIR.glob("*.jsonl"):
        try:
            if jsonl_path.stat().st_mtime < cutoff:
                jsonl_path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def storage_path() -> str:
    return str(STORAGE_DIR)


def storage_is_writable() -> bool:
    return _is_storage_writable()
