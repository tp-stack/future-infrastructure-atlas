"""Domain models for site selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MissingDataFlag(str, Enum):
    GRID_CAPACITY_UNKNOWN = "GRID_CAPACITY_UNKNOWN"
    SUBSTATION_CAPACITY_ESTIMATED = "SUBSTATION_CAPACITY_ESTIMATED"
    FIBER_AVAILABILITY_UNKNOWN = "FIBER_AVAILABILITY_UNKNOWN"
    ZONING_NOT_VERIFIED = "ZONING_NOT_VERIFIED"
    LAND_OWNERSHIP_UNKNOWN = "LAND_OWNERSHIP_UNKNOWN"
    PERMITTING_TIMELINE_UNKNOWN = "PERMITTING_TIMELINE_UNKNOWN"
    WATER_ACCESS_UNKNOWN = "WATER_ACCESS_UNKNOWN"
    COMMERCIAL_PPA_NOT_VERIFIED = "COMMERCIAL_PPA_NOT_VERIFIED"
    CLIMATE_RISK_PROXY_ONLY = "CLIMATE_RISK_PROXY_ONLY"
    REGULATORY_SCORE_COUNTRY_LEVEL_ONLY = "REGULATORY_SCORE_COUNTRY_LEVEL_ONLY"
    MARKET_DEMAND_PROXY_ONLY = "MARKET_DEMAND_PROXY_ONLY"
    ADMIN_GEOCODING_NOT_AVAILABLE = "ADMIN_GEOCODING_NOT_AVAILABLE"
    PROTECTED_AREA_PROXIMITY_OBSERVED = "PROTECTED_AREA_PROXIMITY_OBSERVED"
    CABLE_LANDING_UNKNOWN = "CABLE_LANDING_UNKNOWN"


class EvidenceQuality(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    PROXY = "proxy"
    MISSING = "missing"
    UNVERIFIED = "unverified"


@dataclass
class ComputeProfile:
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
    min_area_ha: float = 0.1


@dataclass
class ScoringProfile:
    key: str
    name: str
    description: str
    weights: dict[str, float]
    confidence_weights: dict[str, float] | None = None


@dataclass
class ExclusionResult:
    excluded: bool
    reasons: list[str] = field(default_factory=list)
    hard_exclusions: list[str] = field(default_factory=list)
    soft_constraints: list[str] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    grid_score: float = 0.0
    fiber_score: float = 0.0
    cable_score: float = 0.0
    land_score: float = 0.0
    climate_score: float = 0.0
    water_score: float = 0.0
    regulatory_score: float = 0.0
    market_score: float = 0.0
    incentive_score: float = 0.0


@dataclass
class ConfidenceBreakdown:
    data_completeness_score: float = 0.0
    source_quality_score: float = 0.0
    freshness_score: float = 0.0
    spatial_precision_score: float = 0.0


@dataclass
class GapRegisterItem:
    category: str
    status: str
    impact: str
    risk: str
    action_required: str
    flag_key: str


@dataclass
class CandidateSite:
    candidate_site_id: str
    country: str
    region: str
    municipality: str
    lat: float
    lon: float
    geometry: dict[str, Any]
    area_ha: float
    compute_profile: str
    nearest_substation_km: float | None = None
    substation_voltage_kv: float | None = None
    estimated_grid_capacity_mw: float | None = None
    grid_connection_confidence: float | None = None
    nearest_power_line_km: float | None = None
    nearest_high_voltage_line_kv: float | None = None
    grid_congestion_score: float | None = None
    power_reliability_score: float | None = None
    nearest_fiber_km: float | None = None
    nearest_ixp_km: float | None = None
    fiber_proxy_level: str | None = None
    fiber_diversity_score: float | None = None
    nearest_cable_landing_km: float | None = None
    nearest_protected_area_km: float | None = None
    latency_proxy_score: float | None = None
    industrial_land_score: float | None = None
    zoning_compatibility_score: float | None = None
    brownfield_score: float | None = None
    permitting_complexity_score: float | None = None
    heat_risk_score: float | None = None
    flood_risk_score: float | None = None
    water_stress_score: float | None = None
    seismic_risk_score: float | None = None
    wildfire_risk_score: float | None = None
    data_sovereignty_score: float | None = None
    regulatory_stability_score: float | None = None
    political_risk_score: float | None = None
    security_risk_score: float | None = None
    market_demand_score: float | None = None
    ai_cluster_score: float | None = None
    enterprise_proximity_score: float | None = None
    incentive_score: float | None = None
    grid_score: float = 0.0
    fiber_score: float = 0.0
    cable_score: float = 0.0
    land_score: float = 0.0
    climate_score: float = 0.0
    water_score: float = 0.0
    regulatory_score: float = 0.0
    market_score: float = 0.0
    final_score: float = 0.0
    confidence_score: float = 0.0
    missing_data_flags: list[str] = field(default_factory=list)
    human_review_required: bool = False
    evidence_summary: str = ""
    excluded: bool = False
    exclusion_reasons: list[str] = field(default_factory=list)
    soft_constraints: list[str] = field(default_factory=list)
    rank: int = 0
    score_breakdown: ScoreBreakdown | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None
    grid_evidence_quality: str | None = None
    fiber_evidence_quality: str | None = None
    land_evidence_quality: str | None = None
    climate_evidence_quality: str | None = None
    water_evidence_quality: str | None = None
    regulatory_evidence_quality: str | None = None
    market_evidence_quality: str | None = None
    due_diligence_gaps: list[GapRegisterItem] | None = None
