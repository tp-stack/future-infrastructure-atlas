"""Report builder for export of site selection results."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from atlas.site_selection.models import CandidateSite

DISCLAIMER_TEXT = (
    "This system does not provide engineering, legal, permitting, grid-connection, investment, tax, "
    "environmental or regulatory advice. All candidate locations require independent technical, legal, "
    "grid, environmental and permitting due diligence."
)


def _candidate_to_dict(candidate: CandidateSite) -> dict[str, Any]:
    return {
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
        "missing_data_flags": candidate.missing_data_flags,
        "human_review_required": candidate.human_review_required,
        "evidence_summary": candidate.evidence_summary,
        "excluded": candidate.excluded,
        "exclusion_reasons": candidate.exclusion_reasons,
        "soft_constraints": candidate.soft_constraints,
    }


def _due_diligence_checklist() -> list[str]:
    return [
        "Independent grid capacity study",
        "Fiber route diversity audit",
        "Land title and zoning verification",
        "Environmental impact assessment",
        "Flood risk and climate resilience study",
        "Water availability and cooling feasibility",
        "Permitting timeline and regulatory pathway",
        "Tax incentive and grant eligibility verification",
        "Community and stakeholder engagement plan",
        "Security and physical site assessment",
    ]


def build_json_report(candidates: list[CandidateSite], query_params: dict[str, Any] | None = None) -> str:
    report: dict[str, Any] = {
        "report_type": "compute_site_selection",
        "version": "1.0",
        "query": query_params or {},
        "candidates": [_candidate_to_dict(c) for c in candidates],
        "due_diligence_checklist": _due_diligence_checklist(),
        "disclaimer": DISCLAIMER_TEXT,
        "metadata": {
            "generated_by": "Future Infrastructure Atlas Compute Site Selection Engine",
            "disclaimer": DISCLAIMER_TEXT,
        },
    }
    return json.dumps(report, indent=2, default=str)


def build_csv_report(candidates: list[CandidateSite]) -> str:
    output = io.StringIO()
    fieldnames = [
        "rank",
        "candidate_site_id",
        "lat",
        "lon",
        "country",
        "region",
        "final_score",
        "confidence_score",
        "grid_score",
        "fiber_score",
        "land_score",
        "climate_score",
        "water_score",
        "regulatory_score",
        "market_score",
        "incentive_score",
        "nearest_substation_km",
        "nearest_fiber_km",
        "nearest_ixp_km",
        "estimated_grid_capacity_mw",
        "human_review_required",
        "excluded",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for c in candidates:
        writer.writerow(_candidate_to_dict(c))
    output.write(f"\n\nDISCLAIMER: {DISCLAIMER_TEXT}")
    return output.getvalue()


def build_pdf_report_structure(candidates: list[CandidateSite], query_params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "title": "Compute Site Selection Report",
        "version": "1.0",
        "disclaimer": DISCLAIMER_TEXT,
        "query": query_params or {},
        "due_diligence_checklist": _due_diligence_checklist(),
        "candidates": [_candidate_to_dict(c) for c in candidates],
        "notes": "PDF-ready structure. Render with a PDF generation library such as weasyprint or reportlab.",
    }
