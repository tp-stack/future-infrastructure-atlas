"""Exclusion engine for compute site selection."""

from __future__ import annotations

from atlas.site_selection.models import CandidateSite, ExclusionResult, MissingDataFlag, ComputeProfile


def check_exclusions(candidate: CandidateSite, profile: ComputeProfile) -> ExclusionResult:
    result = ExclusionResult(excluded=False)

    area_ha = candidate.area_ha if candidate.area_ha > 0 else profile.preferred_area_ha

    if candidate.flood_risk_score is not None and candidate.flood_risk_score > 80:
        result.soft_constraints.append("High flood risk score may affect site viability — environmental due diligence required.")

    if candidate.seismic_risk_score is not None and candidate.seismic_risk_score > 85:
        result.soft_constraints.append("High seismic risk score — structural engineering assessment recommended.")

    if candidate.wildfire_risk_score is not None and candidate.wildfire_risk_score > 90:
        result.soft_constraints.append("Extreme wildfire risk score — wildfire mitigation assessment recommended.")

    if candidate.nearest_substation_km is not None and candidate.nearest_substation_km > profile.max_substation_distance_km * 2:
        result.hard_exclusions.append(
            f"Nearest substation is {candidate.nearest_substation_km:.1f} km away, exceeding {profile.max_substation_distance_km * 2:.0f} km hard limit for {profile.name}."
        )
        result.excluded = True

    grid_ok = candidate.estimated_grid_capacity_mw is not None and candidate.estimated_grid_capacity_mw >= profile.min_power_mw * 0.5

    if not grid_ok and candidate.nearest_substation_km is None and candidate.nearest_power_line_km is None:
        result.hard_exclusions.append(
            f"No power infrastructure detected within range. Grid capacity cannot be estimated for {profile.name} requiring {profile.min_power_mw} MW."
        )
        result.excluded = True

    if candidate.nearest_fiber_km is not None and candidate.nearest_fiber_km > profile.max_fiber_distance_km * 2:
        result.hard_exclusions.append(
            f"Nearest fiber is {candidate.nearest_fiber_km:.1f} km away, exceeding {profile.max_fiber_distance_km * 2:.0f} km hard limit for {profile.name}."
        )
        result.excluded = True

    if area_ha < profile.min_area_ha:
        result.hard_exclusions.append(
            f"Site area ({area_ha:.1f} ha) is below minimum ({profile.min_area_ha:.1f} ha) for {profile.name}."
        )
        result.excluded = True

    if candidate.nearest_protected_area_km is not None and candidate.nearest_protected_area_km < 2.0:
        result.soft_constraints.append("Within 2 km of a protected area (OSM centroid data) — environmental due diligence required.")

    if candidate.water_stress_score is not None and candidate.water_stress_score > 90:
        result.soft_constraints.append("Extreme water stress may affect cooling viability.")

    if candidate.political_risk_score is not None and candidate.political_risk_score > 75:
        result.soft_constraints.append("High political risk score may affect long-term operational stability.")

    if candidate.heat_risk_score is not None and candidate.heat_risk_score > 80:
        result.soft_constraints.append("High heat risk may increase cooling costs and reduce PUE efficiency.")

    result.reasons = result.hard_exclusions + result.soft_constraints
    candidate.excluded = result.excluded
    candidate.exclusion_reasons = result.hard_exclusions
    candidate.soft_constraints = result.soft_constraints

    return result
