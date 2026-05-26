"""FastAPI routes for compute site selection."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException

from atlas.site_selection.candidate_generator import (
    generate_candidates_from_bbox,
    generate_candidates_from_polygon,
)
from atlas.site_selection.infrastructure_index import get_feature_counts, get_index_path, get_index_size_bytes
from atlas.site_selection.models import CandidateSite, MissingDataFlag
from atlas.site_selection.persistence import DISCLAIMER_TEXT, load_candidate, load_candidates_by_ids, storage_path, storage_is_writable
from atlas.site_selection.profiles import COMPUTE_PROFILES, SCORING_PROFILES
from atlas.site_selection.report_builder import (
    _due_diligence_checklist,
    build_csv_report,
    build_json_report,
    build_pdf_report_structure,
)
from atlas.site_selection.schemas import (
    CandidateDetailResponse,
    CandidateSiteResponse,
    ComputeProfileResponse,
    ExportReportRequest,
    ExportReportResponse,
    QueryRequest,
    QueryResponse,
    ScorePointRequest,
    ScorePointResponse,
    ScoringProfileResponse,
)

router = APIRouter(prefix="/v1/site-selection", tags=["site-selection"])

FINAL_OUTPUT_DISCLAIMER = DISCLAIMER_TEXT


def _candidate_to_response(c: CandidateSite) -> CandidateSiteResponse:
    return CandidateSiteResponse(
        rank=c.rank,
        candidate_site_id=c.candidate_site_id,
        lat=c.lat,
        lon=c.lon,
        country=c.country,
        region=c.region,
        municipality=c.municipality,
        area_ha=c.area_ha,
        compute_profile=c.compute_profile,
        final_score=c.final_score,
        confidence_score=c.confidence_score,
        grid_score=c.grid_score,
        fiber_score=c.fiber_score,
        cable_score=c.cable_score,
        land_score=c.land_score,
        climate_score=c.climate_score,
        water_score=c.water_score,
        regulatory_score=c.regulatory_score,
        market_score=c.market_score,
        incentive_score=c.incentive_score,
        missing_data_flags=c.missing_data_flags,
        human_review_required=c.human_review_required,
        evidence_summary=c.evidence_summary,
        excluded=c.excluded,
        exclusion_reasons=c.exclusion_reasons,
        soft_constraints=c.soft_constraints,
        nearest_substation_km=c.nearest_substation_km,
        nearest_fiber_km=c.nearest_fiber_km,
        nearest_ixp_km=c.nearest_ixp_km,
        estimated_grid_capacity_mw=c.estimated_grid_capacity_mw,
        flood_risk_score=c.flood_risk_score,
        water_stress_score=c.water_stress_score,
        regulatory_stability_score=c.regulatory_stability_score,
    )


SOURCE_QUALITY_NOTES: dict[str, str] = {
    MissingDataFlag.GRID_CAPACITY_UNKNOWN.value: "Grid capacity not verified — requires utility interconnection study.",
    MissingDataFlag.SUBSTATION_CAPACITY_ESTIMATED.value: "Substation capacity is estimated from proximity, not utility data.",
    MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value: "Fiber availability not confirmed — requires carrier diversity audit.",
    MissingDataFlag.ZONING_NOT_VERIFIED.value: "Zoning not verified — requires municipal permitting review.",
    MissingDataFlag.LAND_OWNERSHIP_UNKNOWN.value: "Land ownership unknown — requires title search and acquisition feasibility.",
    MissingDataFlag.PERMITTING_TIMELINE_UNKNOWN.value: "Permitting timeline unknown — requires regulatory pathway assessment.",
    MissingDataFlag.WATER_ACCESS_UNKNOWN.value: "Water access not confirmed — requires utility and hydrological study.",
    MissingDataFlag.COMMERCIAL_PPA_NOT_VERIFIED.value: "Commercial PPA not secured — requires energy market analysis.",
    MissingDataFlag.CLIMATE_RISK_PROXY_ONLY.value: "Climate risk assessment is proxy-based — requires site-specific study.",
    MissingDataFlag.REGULATORY_SCORE_COUNTRY_LEVEL_ONLY.value: "Regulatory score is country-level — local conditions may differ.",
    MissingDataFlag.MARKET_DEMAND_PROXY_ONLY.value: "Market demand is proxy-based — requires commercial validation.",
    MissingDataFlag.ADMIN_GEOCODING_NOT_AVAILABLE.value: "Administrative boundary lookup not available — country/region not verified.",
}


def _build_detail_from_record(record: dict[str, Any]) -> CandidateDetailResponse:
    flags = record.get("missing_data_flags") or []

    source_notes = []
    for flag in flags:
        note = SOURCE_QUALITY_NOTES.get(flag)
        if note:
            source_notes.append(note)

    proxy_assumptions = []
    if MissingDataFlag.GRID_CAPACITY_UNKNOWN.value in flags:
        proxy_assumptions.append("Grid capacity is assumed based on substation proximity; actual capacity unknown.")
    if MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value in flags:
        proxy_assumptions.append("Fiber availability is assumed; no carrier commitment confirmed.")
    if MissingDataFlag.CLIMATE_RISK_PROXY_ONLY.value in flags:
        proxy_assumptions.append("Climate risk scores are derived from coarse global proxies, not site surveys.")
    if MissingDataFlag.REGULATORY_SCORE_COUNTRY_LEVEL_ONLY.value in flags:
        proxy_assumptions.append("Regulatory scores reflect national conditions; local zoning and permitting may differ.")
    if MissingDataFlag.MARKET_DEMAND_PROXY_ONLY.value in flags:
        proxy_assumptions.append("Market demand is estimated from regional proxies, not confirmed offtake.")
    if MissingDataFlag.ADMIN_GEOCODING_NOT_AVAILABLE.value in flags:
        proxy_assumptions.append("Administrative boundaries are unverified; country/region/municipality may be inaccurate.")
    if not proxy_assumptions:
        proxy_assumptions.append("All scores are based on available data. Independent verification is required.")

    breakdown = {
        "grid_score": record.get("grid_score", 0),
        "fiber_score": record.get("fiber_score", 0),
        "land_score": record.get("land_score", 0),
        "climate_score": record.get("climate_score", 0),
        "water_score": record.get("water_score", 0),
        "regulatory_score": record.get("regulatory_score", 0),
        "market_score": record.get("market_score", 0),
        "incentive_score": record.get("incentive_score", 0),
    }

    return CandidateDetailResponse(
        candidate_site_id=record["candidate_site_id"],
        query_id=record.get("query_id", ""),
        rank=record.get("rank", 0),
        lat=record.get("lat", 0),
        lon=record.get("lon", 0),
        country=record.get("country", "Unknown"),
        region=record.get("region", "Unknown"),
        municipality=record.get("municipality", "Unknown"),
        area_ha=record.get("area_ha", 0),
        compute_profile=record.get("compute_profile", ""),
        final_score=record.get("final_score", 0),
        confidence_score=record.get("confidence_score", 0),
        score_breakdown=breakdown,
        missing_data_flags=flags,
        human_review_required=record.get("human_review_required", False),
        evidence_summary=record.get("evidence_summary", ""),
        excluded=record.get("excluded", False),
        exclusion_reasons=record.get("exclusion_reasons") or [],
        soft_constraints=record.get("soft_constraints") or [],
        due_diligence_checklist=_due_diligence_checklist(),
        source_quality_notes=source_notes,
        proxy_assumptions=proxy_assumptions,
        disclaimer=FINAL_OUTPUT_DISCLAIMER,
    )


@router.get("/profiles", response_model=dict[str, Any])
def list_profiles() -> dict[str, Any]:
    compute = [
        ComputeProfileResponse(
            key=p.key,
            name=p.name,
            description=p.description,
            min_power_mw=p.min_power_mw,
            preferred_area_ha=p.preferred_area_ha,
            max_substation_distance_km=p.max_substation_distance_km,
            max_fiber_distance_km=p.max_fiber_distance_km,
            latency_priority=p.latency_priority,
            grid_priority=p.grid_priority,
            regulatory_priority=p.regulatory_priority,
            typical_use_case=p.typical_use_case,
        )
        for p in COMPUTE_PROFILES.values()
    ]
    scoring = [
        ScoringProfileResponse(
            key=p.key,
            name=p.name,
            description=p.description,
            weights=p.weights,
        )
        for p in SCORING_PROFILES.values()
    ]
    return {
        "compute_profiles": [c.model_dump() for c in compute],
        "scoring_profiles": [s.model_dump() for s in scoring],
    }


@router.post("/query", response_model=QueryResponse)
def query_candidates(request: QueryRequest) -> QueryResponse:
    MAX_SAFE_LIMIT = 100
    safe_limit = min(request.limit, MAX_SAFE_LIMIT)
    if safe_limit != request.limit:
        request.limit = safe_limit

    profile_key = request.profile
    scoring_profile_key = request.scoring_profile

    if profile_key not in COMPUTE_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown compute profile: {profile_key}")
    if scoring_profile_key not in SCORING_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown scoring profile: {scoring_profile_key}")

    area_type = request.area.get("type")
    coords = request.area.get("coordinates")

    try:
        if area_type == "bbox":
            bbox = tuple(coords)
            candidates, query_id = generate_candidates_from_bbox(
                bbox=bbox,
                profile_key=profile_key,
                scoring_profile_key=scoring_profile_key,
                limit=request.limit,
                include_excluded=request.include_excluded,
            )
        elif area_type == "polygon":
            candidates, query_id = generate_candidates_from_polygon(
                polygon=coords,
                profile_key=profile_key,
                scoring_profile_key=scoring_profile_key,
                limit=request.limit,
                include_excluded=request.include_excluded,
            )
        else:
            raise HTTPException(status_code=400, detail="area.type must be 'bbox' or 'polygon'")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return QueryResponse(
        candidates=[_candidate_to_response(c) for c in candidates],
        count=len(candidates),
        query_id=query_id,
        profile=profile_key,
        scoring_profile=scoring_profile_key,
        area=request.area,
        metadata={
            "disclaimer": FINAL_OUTPUT_DISCLAIMER,
            "generated_by": "Future Infrastructure Atlas Compute Site Selection Engine",
        },
    )


@router.post("/score-point", response_model=ScorePointResponse)
def score_single_point(request: ScorePointRequest) -> ScorePointResponse:
    profile_key = request.profile
    scoring_profile_key = request.scoring_profile

    if profile_key not in COMPUTE_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown compute profile: {profile_key}")

    bbox = (request.lon - 0.01, request.lat - 0.01, request.lon + 0.01, request.lat + 0.01)

    candidates, _query_id = generate_candidates_from_bbox(
        bbox=bbox,
        profile_key=profile_key,
        scoring_profile_key=scoring_profile_key,
        limit=1,
        include_excluded=True,
    )

    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates could be generated for this point.")

    c = candidates[0]
    return ScorePointResponse(
        candidate_site_id=c.candidate_site_id,
        lat=c.lat,
        lon=c.lon,
        country=c.country,
        region=c.region,
        municipality=c.municipality,
        final_score=c.final_score,
        confidence_score=c.confidence_score,
        score_breakdown={
            "grid_score": c.grid_score,
            "fiber_score": c.fiber_score,
            "land_score": c.land_score,
            "climate_score": c.climate_score,
            "water_score": c.water_score,
            "regulatory_score": c.regulatory_score,
            "market_score": c.market_score,
            "incentive_score": c.incentive_score,
        },
        missing_data_flags=c.missing_data_flags,
        human_review_required=c.human_review_required,
        evidence_summary=c.evidence_summary,
        excluded=c.excluded,
        exclusion_reasons=c.exclusion_reasons,
    )


@router.get("/candidate/{candidate_site_id}", response_model=CandidateDetailResponse)
def get_candidate_detail(candidate_site_id: str) -> CandidateDetailResponse:
    record = load_candidate(candidate_site_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_site_id} not found. Candidates must be generated via POST /v1/site-selection/query first.",
        )
    return _build_detail_from_record(record)


@router.post("/export-report", response_model=ExportReportResponse)
def export_report(request: ExportReportRequest) -> ExportReportResponse:
    records = load_candidates_by_ids(request.candidate_ids)
    if not records:
        raise HTTPException(
            status_code=404,
            detail="No candidates found for the provided IDs. Generate candidates via POST /v1/site-selection/query first.",
        )

    records.sort(key=lambda r: r.get("rank", 999))

    if request.format == "json":
        report_data = {
            "report_type": "compute_site_selection",
            "format": "json",
            "candidate_count": len(records),
            "candidates": records,
            "due_diligence_checklist": _due_diligence_checklist(),
            "disclaimer": FINAL_OUTPUT_DISCLAIMER,
            "generated_by": "Future Infrastructure Atlas Compute Site Selection Engine",
        }
        return ExportReportResponse(
            report_type="compute_site_selection",
            format="json",
            candidate_count=len(records),
            content=report_data,
            disclaimer=FINAL_OUTPUT_DISCLAIMER,
        )

    elif request.format == "csv":
        # Build CSV from stored records
        import csv
        import io

        output = io.StringIO()
        fieldnames = [
            "rank", "candidate_site_id", "lat", "lon", "country", "region",
            "final_score", "confidence_score", "grid_score", "fiber_score",
            "land_score", "climate_score", "water_score", "regulatory_score",
            "market_score", "incentive_score", "nearest_substation_km",
            "nearest_fiber_km", "human_review_required", "excluded",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)
        output.write(f"\n\nDISCLAIMER: {FINAL_OUTPUT_DISCLAIMER}")

        return ExportReportResponse(
            report_type="compute_site_selection",
            format="csv",
            candidate_count=len(records),
            content=output.getvalue(),
            disclaimer=FINAL_OUTPUT_DISCLAIMER,
        )

    elif request.format == "pdf_ready_json":
        pdf_structure = {
            "title": "Compute Site Selection Report",
            "format": "pdf_ready_json",
            "version": "1.0",
            "disclaimer": FINAL_OUTPUT_DISCLAIMER,
            "due_diligence_checklist": _due_diligence_checklist(),
            "candidates": records,
            "notes": "PDF-ready structure. Render with a PDF generation library such as weasyprint or reportlab.",
        }
        return ExportReportResponse(
            report_type="compute_site_selection",
            format="pdf_ready_json",
            candidate_count=len(records),
            content=pdf_structure,
            disclaimer=FINAL_OUTPUT_DISCLAIMER,
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")


@router.get("/health")
def health() -> dict[str, Any]:
    index_counts = get_feature_counts()
    return {
        "status": "ok",
        "module": "site_selection",
        "storage_path": storage_path(),
        "storage_writable": str(storage_is_writable()),
        "infrastructure_index": {
            "path": get_index_path(),
            "size_bytes": get_index_size_bytes(),
            "feature_counts": index_counts,
            "total_features": sum(index_counts.values()),
        },
    }


def register_site_selection_routes(app: FastAPI) -> None:
    app.include_router(router)
