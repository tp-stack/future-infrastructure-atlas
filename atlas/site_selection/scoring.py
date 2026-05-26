"""Deterministic scoring engine for compute site selection."""

from __future__ import annotations

from atlas.site_selection.models import CandidateSite, MissingDataFlag, ScoreBreakdown
from atlas.site_selection.profiles import SCORING_PROFILES, validate_weights

SCORE_MIN = 0.0
SCORE_MAX = 100.0


def _clamp(value: float, lo: float = SCORE_MIN, hi: float = SCORE_MAX) -> float:
    return max(lo, min(hi, value))


def _distance_score(distance_km: float, max_good_km: float, max_acceptable_km: float) -> float:
    if distance_km <= max_good_km:
        return 100.0
    if distance_km >= max_acceptable_km:
        return 0.0
    ratio = (distance_km - max_good_km) / (max_acceptable_km - max_good_km)
    return _clamp(100.0 * (1.0 - ratio))


def _inverse_distance_score(distance_km: float, max_acceptable_km: float) -> float:
    if distance_km <= 0:
        return 100.0
    if distance_km >= max_acceptable_km:
        return 0.0
    return _clamp(100.0 * (1.0 - distance_km / max_acceptable_km))


def compute_grid_score(candidate: CandidateSite, profile) -> tuple[float, list[str]]:
    flags: list[str] = []
    has_substation = candidate.nearest_substation_km is not None
    has_power_line = candidate.nearest_power_line_km is not None

    if has_substation:
        sub_score = _distance_score(candidate.nearest_substation_km, 1.0, profile.max_substation_distance_km * 1.5)
    elif has_power_line:
        sub_score = _distance_score(candidate.nearest_power_line_km, 0.5, profile.max_substation_distance_km * 1.5)
    else:
        sub_score = 20.0
        flags.append(MissingDataFlag.GRID_CAPACITY_UNKNOWN.value)

    capacity_score = 50.0
    if candidate.estimated_grid_capacity_mw is not None:
        if candidate.estimated_grid_capacity_mw >= profile.min_power_mw * 2:
            capacity_score = 100.0
        elif candidate.estimated_grid_capacity_mw >= profile.min_power_mw:
            capacity_score = 75.0
        elif candidate.estimated_grid_capacity_mw >= profile.min_power_mw * 0.5:
            capacity_score = 50.0
        else:
            capacity_score = 25.0
    else:
        flags.append(MissingDataFlag.SUBSTATION_CAPACITY_ESTIMATED.value)

    congestion = candidate.grid_congestion_score if candidate.grid_congestion_score is not None else 50.0
    reliability = candidate.power_reliability_score if candidate.power_reliability_score is not None else 50.0

    score = 0.4 * sub_score + 0.3 * capacity_score + 0.15 * _clamp(congestion) + 0.15 * _clamp(reliability)
    return _clamp(score), flags


def compute_fiber_score(candidate: CandidateSite, profile) -> tuple[float, list[str]]:
    flags: list[str] = []
    has_fiber = candidate.nearest_fiber_km is not None
    has_ixp = candidate.nearest_ixp_km is not None

    if has_fiber:
        fiber_dist_score = _distance_score(candidate.nearest_fiber_km, 0.5, profile.max_fiber_distance_km * 1.5)
    else:
        fiber_dist_score = 20.0
        flags.append(MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value)

    if has_ixp:
        ixp_score = _distance_score(candidate.nearest_ixp_km, 10.0, 100.0)
    else:
        ixp_score = 40.0

    diversity = candidate.fiber_diversity_score if candidate.fiber_diversity_score is not None else 50.0
    latency = candidate.latency_proxy_score if candidate.latency_proxy_score is not None else 50.0

    score = 0.4 * fiber_dist_score + 0.2 * ixp_score + 0.2 * _clamp(diversity) + 0.2 * _clamp(latency)
    return _clamp(score), flags


def compute_land_score(candidate: CandidateSite) -> tuple[float, list[str]]:
    flags: list[str] = []

    industrial = candidate.industrial_land_score if candidate.industrial_land_score is not None else 50.0
    zoning = candidate.zoning_compatibility_score if candidate.zoning_compatibility_score is not None else 50.0
    brownfield = candidate.brownfield_score if candidate.brownfield_score is not None else 50.0
    permitting = candidate.permitting_complexity_score if candidate.permitting_complexity_score is not None else 50.0

    if candidate.zoning_compatibility_score is None:
        flags.append(MissingDataFlag.ZONING_NOT_VERIFIED.value)
    if candidate.industrial_land_score is None:
        flags.append(MissingDataFlag.LAND_OWNERSHIP_UNKNOWN.value)
    if candidate.permitting_complexity_score is None:
        flags.append(MissingDataFlag.PERMITTING_TIMELINE_UNKNOWN.value)

    score = 0.3 * _clamp(industrial) + 0.3 * _clamp(zoning) + 0.2 * _clamp(brownfield) + 0.2 * _clamp(permitting)
    return _clamp(score), flags


def compute_climate_score(candidate: CandidateSite) -> tuple[float, list[str]]:
    flags: list[str] = []
    heat = candidate.heat_risk_score if candidate.heat_risk_score is not None else 50.0
    flood = candidate.flood_risk_score if candidate.flood_risk_score is not None else 50.0
    seismic = candidate.seismic_risk_score if candidate.seismic_risk_score is not None else 50.0
    wildfire = candidate.wildfire_risk_score if candidate.wildfire_risk_score is not None else 50.0

    if candidate.heat_risk_score is None:
        flags.append(MissingDataFlag.CLIMATE_RISK_PROXY_ONLY.value)

    score = 0.35 * (100.0 - _clamp(heat)) + 0.35 * (100.0 - _clamp(flood)) + 0.15 * (100.0 - _clamp(seismic)) + 0.15 * (100.0 - _clamp(wildfire))
    return _clamp(score), flags


def compute_water_score(candidate: CandidateSite) -> tuple[float, list[str]]:
    flags: list[str] = []
    water_stress = candidate.water_stress_score if candidate.water_stress_score is not None else 50.0

    if candidate.water_stress_score is None:
        flags.append(MissingDataFlag.WATER_ACCESS_UNKNOWN.value)

    return _clamp(100.0 - water_stress), flags


def compute_regulatory_score(candidate: CandidateSite) -> tuple[float, list[str]]:
    flags: list[str] = []
    sovereignty = candidate.data_sovereignty_score if candidate.data_sovereignty_score is not None else 50.0
    stability = candidate.regulatory_stability_score if candidate.regulatory_stability_score is not None else 50.0
    political = candidate.political_risk_score if candidate.political_risk_score is not None else 50.0
    security = candidate.security_risk_score if candidate.security_risk_score is not None else 50.0

    if candidate.regulatory_stability_score is None:
        flags.append(MissingDataFlag.REGULATORY_SCORE_COUNTRY_LEVEL_ONLY.value)

    score = 0.3 * _clamp(sovereignty) + 0.3 * _clamp(stability) + 0.2 * (100.0 - _clamp(political)) + 0.2 * (100.0 - _clamp(security))
    return _clamp(score), flags


def compute_market_score(candidate: CandidateSite) -> tuple[float, list[str]]:
    flags: list[str] = []
    demand = candidate.market_demand_score if candidate.market_demand_score is not None else 50.0
    ai_cluster = candidate.ai_cluster_score if candidate.ai_cluster_score is not None else 50.0
    enterprise = candidate.enterprise_proximity_score if candidate.enterprise_proximity_score is not None else 50.0

    if candidate.market_demand_score is None:
        flags.append(MissingDataFlag.MARKET_DEMAND_PROXY_ONLY.value)

    score = 0.4 * _clamp(demand) + 0.3 * _clamp(ai_cluster) + 0.3 * _clamp(enterprise)
    return _clamp(score), flags


def compute_cable_score(candidate: CandidateSite) -> tuple[float, list[str]]:
    flags: list[str] = []
    if candidate.nearest_cable_landing_km is not None:
        score = _distance_score(candidate.nearest_cable_landing_km, 5.0, 100.0)
    else:
        score = 30.0
        flags.append(MissingDataFlag.CABLE_LANDING_UNKNOWN.value)
    return _clamp(score), flags


def compute_incentive_score(candidate: CandidateSite) -> float:
    return _clamp(candidate.incentive_score if candidate.incentive_score is not None else 30.0)


def compute_final_score(scores: ScoreBreakdown, scoring_profile_key: str = "default") -> float:
    profile = SCORING_PROFILES.get(scoring_profile_key)
    if profile is None:
        profile = SCORING_PROFILES["default"]

    if not validate_weights(profile.weights):
        profile = SCORING_PROFILES["default"]

    total = (
        profile.weights.get("grid_score", 0.3) * scores.grid_score
        + profile.weights.get("fiber_score", 0.2) * scores.fiber_score
        + profile.weights.get("cable_score", 0.0) * scores.cable_score
        + profile.weights.get("land_score", 0.15) * scores.land_score
        + profile.weights.get("climate_score", 0.1) * scores.climate_score
        + profile.weights.get("water_score", 0.0) * scores.water_score
        + profile.weights.get("regulatory_score", 0.1) * scores.regulatory_score
        + profile.weights.get("market_score", 0.1) * scores.market_score
        + profile.weights.get("incentive_score", 0.05) * scores.incentive_score
    )
    return _clamp(total)


def score_candidate(candidate: CandidateSite, profile, scoring_profile_key: str = "default") -> tuple[ScoreBreakdown, list[str]]:
    all_flags: list[str] = []

    grid_score, grid_flags = compute_grid_score(candidate, profile)
    all_flags.extend(grid_flags)

    fiber_score, fiber_flags = compute_fiber_score(candidate, profile)
    all_flags.extend(fiber_flags)

    land_score, land_flags = compute_land_score(candidate)
    all_flags.extend(land_flags)

    cable_score, cable_flags = compute_cable_score(candidate)
    all_flags.extend(cable_flags)

    climate_score, climate_flags = compute_climate_score(candidate)
    all_flags.extend(climate_flags)

    water_score, water_flags = compute_water_score(candidate)
    all_flags.extend(water_flags)

    regulatory_score, reg_flags = compute_regulatory_score(candidate)
    all_flags.extend(reg_flags)

    market_score, market_flags = compute_market_score(candidate)
    all_flags.extend(market_flags)

    incentive_score = compute_incentive_score(candidate)

    breakdown = ScoreBreakdown(
        grid_score=grid_score,
        fiber_score=fiber_score,
        cable_score=cable_score,
        land_score=land_score,
        climate_score=climate_score,
        water_score=water_score,
        regulatory_score=regulatory_score,
        market_score=market_score,
        incentive_score=incentive_score,
    )

    final = compute_final_score(breakdown, scoring_profile_key)
    candidate.grid_score = grid_score
    candidate.fiber_score = fiber_score
    candidate.cable_score = cable_score
    candidate.land_score = land_score
    candidate.climate_score = climate_score
    candidate.water_score = water_score
    candidate.regulatory_score = regulatory_score
    candidate.market_score = market_score
    candidate.incentive_score = incentive_score
    candidate.final_score = final
    candidate.score_breakdown = breakdown

    seen = set()
    unique_flags = []
    for f in all_flags:
        if f not in seen:
            seen.add(f)
            unique_flags.append(f)
    candidate.missing_data_flags = unique_flags

    return breakdown, unique_flags
