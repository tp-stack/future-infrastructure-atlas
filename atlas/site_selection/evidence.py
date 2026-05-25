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

    if candidate.flood_risk_score is not None:
        parts.append(f"Flood risk score: {candidate.flood_risk_score:.0f}/100.")
    else:
        parts.append("Flood risk assessment is based on proxy data only.")

    if candidate.water_stress_score is not None:
        parts.append(f"Water stress score: {candidate.water_stress_score:.0f}/100.")

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
