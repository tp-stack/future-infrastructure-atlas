"""Confidence scoring for compute site selection candidates."""

from __future__ import annotations

from atlas.site_selection.models import CandidateSite, ConfidenceBreakdown, MissingDataFlag, ScoringProfile
from atlas.site_selection.profiles import SCORING_PROFILES

SCORE_MIN = 0.0
SCORE_MAX = 100.0


def _clamp(value: float, lo: float = SCORE_MIN, hi: float = SCORE_MAX) -> float:
    return max(lo, min(hi, value))


FLAG_WEIGHTS: dict[str, float] = {
    MissingDataFlag.GRID_CAPACITY_UNKNOWN.value: -15.0,
    MissingDataFlag.SUBSTATION_CAPACITY_ESTIMATED.value: -5.0,
    MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value: -15.0,
    MissingDataFlag.ZONING_NOT_VERIFIED.value: -10.0,
    MissingDataFlag.LAND_OWNERSHIP_UNKNOWN.value: -8.0,
    MissingDataFlag.PERMITTING_TIMELINE_UNKNOWN.value: -5.0,
    MissingDataFlag.WATER_ACCESS_UNKNOWN.value: -8.0,
    MissingDataFlag.COMMERCIAL_PPA_NOT_VERIFIED.value: -5.0,
    MissingDataFlag.CLIMATE_RISK_PROXY_ONLY.value: -5.0,
    MissingDataFlag.REGULATORY_SCORE_COUNTRY_LEVEL_ONLY.value: -5.0,
    MissingDataFlag.MARKET_DEMAND_PROXY_ONLY.value: -5.0,
    MissingDataFlag.ADMIN_GEOCODING_NOT_AVAILABLE.value: -5.0,
}


def compute_data_completeness(candidate: CandidateSite) -> float:
    total_fields = 10
    filled = 0

    if candidate.nearest_substation_km is not None:
        filled += 1
    if candidate.nearest_power_line_km is not None:
        filled += 1
    if candidate.nearest_fiber_km is not None:
        filled += 1
    if candidate.nearest_ixp_km is not None:
        filled += 1
    if candidate.estimated_grid_capacity_mw is not None:
        filled += 1
    if candidate.flood_risk_score is not None:
        filled += 1
    if candidate.water_stress_score is not None:
        filled += 1
    if candidate.regulatory_stability_score is not None:
        filled += 1
    if candidate.market_demand_score is not None:
        filled += 1
    if candidate.zoning_compatibility_score is not None:
        filled += 1

    return _clamp((filled / total_fields) * 100.0)


def compute_source_quality(candidate: CandidateSite) -> float:
    flags = set(candidate.missing_data_flags)
    base = 100.0
    for flag in flags:
        deduction = FLAG_WEIGHTS.get(flag, 0.0)
        base += deduction
    return _clamp(base)


def compute_freshness_score(candidate: CandidateSite) -> float:
    return 70.0


def compute_spatial_precision_score(candidate: CandidateSite) -> float:
    return 80.0


def compute_confidence_score(candidate: CandidateSite, scoring_profile_key: str = "default") -> float:
    profile = SCORING_PROFILES.get(scoring_profile_key, SCORING_PROFILES["default"])
    cw = profile.confidence_weights or SCORING_PROFILES["default"].confidence_weights

    completeness = compute_data_completeness(candidate)
    source_quality = compute_source_quality(candidate)
    freshness = compute_freshness_score(candidate)
    spatial = compute_spatial_precision_score(candidate)

    total = (
        cw.get("data_completeness_score", 0.45) * completeness
        + cw.get("source_quality_score", 0.30) * source_quality
        + cw.get("freshness_score", 0.15) * freshness
        + cw.get("spatial_precision_score", 0.10) * spatial
    )

    candidate.confidence_score = _clamp(total)
    candidate.confidence_breakdown = ConfidenceBreakdown(
        data_completeness_score=completeness,
        source_quality_score=source_quality,
        freshness_score=freshness,
        spatial_precision_score=spatial,
    )
    return candidate.confidence_score


def is_human_review_required(candidate: CandidateSite, profile) -> bool:
    if candidate.final_score >= 70 and candidate.confidence_score < 70:
        return True
    if candidate.estimated_grid_capacity_mw is None and profile.min_power_mw > 5:
        return True
    if MissingDataFlag.ZONING_NOT_VERIFIED.value in candidate.missing_data_flags:
        return True
    campus_profiles = ["sovereign_compute_campus_20mw", "hyperscale_ai_campus_100mw"]
    if profile.key in campus_profiles:
        water_unknown = MissingDataFlag.WATER_ACCESS_UNKNOWN.value in candidate.missing_data_flags
        climate_proxy = MissingDataFlag.CLIMATE_RISK_PROXY_ONLY.value in candidate.missing_data_flags
        if water_unknown or climate_proxy:
            return True
    if candidate.regulatory_score is not None and candidate.regulatory_score < 30:
        return True
    return False
