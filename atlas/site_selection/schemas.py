"""Pydantic schemas for site selection API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QueryArea(BaseModel):
    type: str = Field(..., pattern="^(bbox|polygon)$")
    coordinates: list[float] | list[list[list[float]]]


class QueryRequest(BaseModel):
    area: dict[str, Any]
    profile: str = "regional_compute_5mw"
    scoring_profile: str = "default"
    limit: int = Field(default=25, ge=1, le=100)
    include_excluded: bool = False

    @model_validator(mode="after")
    def validate_area(self) -> "QueryRequest":
        area_type = self.area.get("type")
        coords = self.area.get("coordinates")
        if area_type == "bbox":
            if not isinstance(coords, list) or len(coords) != 4:
                raise ValueError("bbox coordinates must be [minLon, minLat, maxLon, maxLat]")
            if not all(isinstance(c, (int, float)) for c in coords):
                raise ValueError("bbox coordinates must be numbers")
        elif area_type == "polygon":
            if not isinstance(coords, list) or len(coords) == 0:
                raise ValueError("polygon coordinates must be a non-empty list of rings")
        else:
            raise ValueError("area.type must be 'bbox' or 'polygon'")
        return self


class ScorePointRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    profile: str = "regional_compute_5mw"
    scoring_profile: str = "default"
    country: str | None = None
    region: str | None = None
    municipality: str | None = None


class ExportReportRequest(BaseModel):
    candidate_ids: list[str] = Field(..., min_length=1, max_length=100)
    format: str = Field(default="json", pattern="^(json|csv|pdf_ready_json)$")
    include_disclaimer: bool = True


class ComputeProfileResponse(BaseModel):
    key: str
    name: str
    description: str
    min_power_mw: float
    preferred_area_ha: float
    max_substation_distance_km: float
    max_fiber_distance_km: float
    latency_priority: str
    grid_priority: str
    regulatory_priority: str
    typical_use_case: str


class ScoringProfileResponse(BaseModel):
    key: str
    name: str
    description: str
    weights: dict[str, float]


class CandidateSiteResponse(BaseModel):
    rank: int
    candidate_site_id: str
    lat: float
    lon: float
    country: str
    region: str
    municipality: str
    area_ha: float
    compute_profile: str
    final_score: float
    confidence_score: float
    grid_score: float
    fiber_score: float
    land_score: float
    climate_score: float
    water_score: float
    regulatory_score: float
    market_score: float
    incentive_score: float
    missing_data_flags: list[str]
    human_review_required: bool
    evidence_summary: str
    excluded: bool
    exclusion_reasons: list[str]
    soft_constraints: list[str]
    nearest_substation_km: float | None = None
    nearest_fiber_km: float | None = None
    nearest_ixp_km: float | None = None
    estimated_grid_capacity_mw: float | None = None
    flood_risk_score: float | None = None
    water_stress_score: float | None = None
    regulatory_stability_score: float | None = None
    incentive_score_raw: float | None = None


class CandidateDetailResponse(BaseModel):
    candidate_site_id: str
    query_id: str
    rank: int
    lat: float
    lon: float
    country: str
    region: str
    municipality: str
    area_ha: float
    compute_profile: str
    final_score: float
    confidence_score: float
    score_breakdown: dict[str, float]
    missing_data_flags: list[str]
    human_review_required: bool
    evidence_summary: str
    excluded: bool
    exclusion_reasons: list[str]
    soft_constraints: list[str]
    due_diligence_checklist: list[str]
    source_quality_notes: list[str]
    proxy_assumptions: list[str]
    disclaimer: str


class ScorePointResponse(BaseModel):
    candidate_site_id: str
    lat: float
    lon: float
    country: str
    region: str
    municipality: str
    final_score: float
    confidence_score: float
    score_breakdown: dict[str, float]
    missing_data_flags: list[str]
    human_review_required: bool
    evidence_summary: str
    excluded: bool
    exclusion_reasons: list[str]


class QueryResponse(BaseModel):
    candidates: list[CandidateSiteResponse]
    count: int
    query_id: str
    profile: str
    scoring_profile: str
    area: dict[str, Any]
    metadata: dict[str, Any]


class ExportReportResponse(BaseModel):
    report_type: str
    format: str
    candidate_count: int
    content: str | dict[str, Any]
    disclaimer: str
