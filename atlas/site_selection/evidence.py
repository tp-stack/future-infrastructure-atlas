"""Evidence generation for compute site selection candidates."""

from __future__ import annotations

from atlas.site_selection.models import CandidateSite, MissingDataFlag


def _grid_proxy_evidence(candidate: CandidateSite) -> str:
    """Build grid proxy evidence sentence distinguishing proxy level."""
    if candidate.nearest_substation_km is None:
        return "No substation or power plant proximity data available — grid capacity is unknown."

    # Try to determine proxy level from flags and voltage data
    is_substation = candidate.substation_voltage_kv is not None
    is_hv_line = candidate.nearest_high_voltage_line_kv is not None and not is_substation
    is_power_plant = candidate.substation_voltage_kv is None and candidate.nearest_high_voltage_line_kv is None

    dist = candidate.nearest_substation_km
    if is_substation:
        parts = [
            f"Nearest OSM substation is approximately {dist:.1f} km away "
            f"(voltage: {candidate.substation_voltage_kv:.0f} kV)."
        ]
        if MissingDataFlag.SUBSTATION_CAPACITY_ESTIMATED.value in candidate.missing_data_flags:
            parts.append("Capacity is estimated from proximity, not utility data.")
        return " ".join(parts)
    elif is_hv_line:
        parts = [
            f"Nearest high-voltage line proxy is approximately {dist:.1f} km away "
            f"(voltage: {candidate.nearest_high_voltage_line_kv:.0f} kV). "
            f"This is a derived proxy point — actual substation distance may differ."
        ]
        return " ".join(parts)
    else:
        return (
            f"Nearest power plant proxy is approximately {dist:.1f} km away. "
            f"This is a weak proxy for grid proximity — actual substation distance is unknown."
        )


_PROXY_LABELS: dict[str, str] = {
    "ixp_proxy": "IXP proxy point (PeeringDB facility with interconnection count > 0)",
    "facility": "PeeringDB facility point",
    "data_center": "data center proxy point",
    "cable_landing": "submarine cable landing proxy point",
}


def _fiber_proxy_evidence(candidate: CandidateSite) -> str:
    """Build fiber proxy evidence sentence distinguishing the proxy tier."""
    if candidate.nearest_fiber_km is None:
        return "Fiber availability is unknown."

    level = candidate.fiber_proxy_level or "data_center"
    label = _PROXY_LABELS.get(level, "proxy point")
    dist = candidate.nearest_fiber_km

    if MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value in candidate.missing_data_flags:
        return (
            f"Nearest {label} is approximately {dist:.1f} km away. "
            f"This is a proxy for fiber connectivity — actual fiber availability is unconfirmed."
        )
    return f"Nearest fiber connectivity is approximately {dist:.1f} km away."


def _land_proxy_evidence(candidate: CandidateSite) -> str:
    """Build land suitability proxy evidence sentence."""
    has_industrial = candidate.industrial_land_score is not None
    has_zoning = candidate.zoning_compatibility_score is not None
    has_brownfield = candidate.brownfield_score is not None
    has_permitting = candidate.permitting_complexity_score is not None

    sentences: list[str] = []

    if has_industrial:
        score = candidate.industrial_land_score
        if score and score >= 70:
            sentences.append(
                f"Industrial zone proxy is favorable (score: {score:.0f}/100) — "
                f"near power plant clusters indicating industrial/utility land use."
            )
        else:
            sentences.append(
                f"Industrial zone proxy is limited (score: {score:.0f}/100) — "
                f"no nearby power plant clusters indicating industrial land use."
            )
    else:
        sentences.append("Industrial land suitability is unknown — no proxy data available.")

    if has_zoning:
        sentences.append(f"Zoning compatibility score: {candidate.zoning_compatibility_score:.0f}/100.")
    else:
        sentences.append("Zoning is not verified — proximity to industrial zones does not confirm zoning approval.")

    if has_brownfield:
        sentences.append(f"Brownfield score: {candidate.brownfield_score:.0f}/100.")
    else:
        sentences.append("Brownfield potential is unknown.")

    if has_permitting:
        sentences.append(f"Permitting complexity score: {candidate.permitting_complexity_score:.0f}/100.")
    else:
        sentences.append("Permitting timeline is unknown — independent assessment required.")

    return " ".join(sentences)


def _environmental_proxy_evidence(candidate: CandidateSite) -> str:
    """Build environmental constraint evidence with source-quality labels."""
    sentences: list[str] = []

    # Flood risk
    if candidate.flood_risk_score is not None:
        sentences.append(f"Flood risk score: {candidate.flood_risk_score:.0f}/100 (source: {'verified' if candidate.flood_risk_score >= 0 else 'unknown'}).")
    else:
        sentences.append("Flood risk assessment is based on proxy data only — no flood hazard dataset available.")

    # Protected area proximity
    if candidate.nearest_protected_area_km is not None:
        sentences.append(
            f"Nearest protected area centroid is {candidate.nearest_protected_area_km:.1f} km away "
            f"(source: OSM boundary=protected_area / leisure=nature_reserve from Geofabrik extracts). "
            f"Proximity does not confirm overlap — polygon boundaries required for hard exclusion."
        )
    else:
        sentences.append("Protected area proximity is unknown — no OSM protected-area data available for this region.")

    # Water stress
    if candidate.water_stress_score is not None:
        sentences.append(f"Water stress score: {candidate.water_stress_score:.0f}/100 (source: {'verified' if candidate.water_stress_score >= 0 else 'unknown'}).")
    else:
        sentences.append("Water stress assessment is based on proxy data only — no water availability data available.")

    # Heat risk
    if candidate.heat_risk_score is not None:
        sentences.append(f"Heat risk score: {candidate.heat_risk_score:.0f}/100.")
    else:
        sentences.append("Heat risk assessment is based on proxy data only — no temperature hazard dataset available.")

    # Seismic risk
    if candidate.seismic_risk_score is not None:
        sentences.append(f"Seismic risk score: {candidate.seismic_risk_score:.0f}/100.")
    else:
        sentences.append("Seismic risk assessment is based on proxy data only — no seismic hazard dataset available.")

    # Wildfire risk
    if candidate.wildfire_risk_score is not None:
        sentences.append(f"Wildfire risk score: {candidate.wildfire_risk_score:.0f}/100.")
    else:
        sentences.append("Wildfire risk assessment is based on proxy data only — no wildfire hazard dataset available.")

    sentences.append("Environmental constraint data is incomplete — independent environmental due diligence is required.")

    return " ".join(sentences)


def generate_evidence_summary(candidate: CandidateSite) -> str:
    parts: list[str] = []

    parts.append(
        f"Candidate location at {candidate.lat:.4f}, {candidate.lon:.4f} ({candidate.country}, {candidate.region}) "
        f"scored {candidate.final_score:.0f}/100 for {candidate.compute_profile} profile."
    )

    parts.append(_grid_proxy_evidence(candidate))

    if candidate.estimated_grid_capacity_mw is not None:
        parts.append(f"Estimated grid capacity: {candidate.estimated_grid_capacity_mw:.0f} MW.")
    else:
        parts.append("Estimated grid capacity is unknown — proxy assessment required.")

    parts.append(_fiber_proxy_evidence(candidate))

    if candidate.nearest_ixp_km is not None:
        parts.append(f"Nearest internet exchange point is approximately {candidate.nearest_ixp_km:.1f} km away.")

    parts.append(_land_proxy_evidence(candidate))

    parts.append(_environmental_proxy_evidence(candidate))

    if candidate.regulatory_stability_score is not None:
        parts.append(f"Regulatory stability score: {candidate.regulatory_stability_score:.0f}/100.")
    else:
        parts.append("Regulatory score is country-level only and may not reflect local conditions.")

    if candidate.human_review_required:
        parts.append("HUMAN REVIEW REQUIRED — confidence is limited or critical data is missing for this profile.")

    if candidate.excluded:
        parts.append("EXCLUDED — " + "; ".join(candidate.exclusion_reasons))

    parts.append(
        "DISCLAIMER: This is preliminary infrastructure intelligence only. "
        "This system does not provide engineering, legal, permitting, grid-connection, investment, tax, "
        "environmental or regulatory advice. All candidate locations require independent technical, legal, "
        "grid, environmental and permitting due diligence."
    )

    return " ".join(parts)
