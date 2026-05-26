"""Tests for site selection scoring engine."""

import pytest
from atlas.site_selection.models import CandidateSite, ScoreBreakdown
from atlas.site_selection.profiles import COMPUTE_PROFILES, SCORING_PROFILES, validate_all_profiles
from atlas.site_selection.scoring import (
    compute_final_score,
    compute_grid_score,
    compute_fiber_score,
    compute_cable_score,
    compute_land_score,
    compute_climate_score,
    compute_water_score,
    compute_regulatory_score,
    compute_market_score,
    score_candidate,
    SCORE_MIN,
    SCORE_MAX,
)


def test_scores_are_in_range():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-1",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    scores, flags = score_candidate(candidate, profile)
    assert SCORE_MIN <= scores.grid_score <= SCORE_MAX
    assert SCORE_MIN <= scores.fiber_score <= SCORE_MAX
    assert SCORE_MIN <= scores.cable_score <= SCORE_MAX
    assert SCORE_MIN <= scores.land_score <= SCORE_MAX
    assert SCORE_MIN <= scores.climate_score <= SCORE_MAX
    assert SCORE_MIN <= scores.water_score <= SCORE_MAX
    assert SCORE_MIN <= scores.regulatory_score <= SCORE_MAX
    assert SCORE_MIN <= scores.market_score <= SCORE_MAX
    assert SCORE_MIN <= scores.incentive_score <= SCORE_MAX
    assert SCORE_MIN <= candidate.final_score <= SCORE_MAX


def test_grid_score_with_substation():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-2",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_substation_km=1.0,
        estimated_grid_capacity_mw=10,
    )
    score, flags, quality = compute_grid_score(candidate, profile)
    assert score > 70
    assert quality is not None
    assert "SUBSTATION_CAPACITY_ESTIMATED" not in flags


def test_grid_score_without_substation():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-3",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    score, flags, quality = compute_grid_score(candidate, profile)
    assert score < 50
    assert quality == "missing"
    assert "GRID_CAPACITY_UNKNOWN" in flags


def test_fiber_score_with_fiber():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-4",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_fiber_km=0.5,
    )
    score, flags, quality = compute_fiber_score(candidate, profile)
    assert score > 60
    assert quality is not None
    assert "FIBER_AVAILABILITY_UNKNOWN" not in flags


def test_fiber_score_without_fiber():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-5",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    score, flags, quality = compute_fiber_score(candidate, profile)
    assert quality == "missing"
    assert "FIBER_AVAILABILITY_UNKNOWN" in flags


def test_missing_data_generates_flags():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-6",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    scores, flags = score_candidate(candidate, profile)
    assert len(flags) > 0
    assert "GRID_CAPACITY_UNKNOWN" in flags
    assert "FIBER_AVAILABILITY_UNKNOWN" in flags


def test_final_score_respects_weights():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-7",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_substation_km=0.5,
        estimated_grid_capacity_mw=50,
        nearest_fiber_km=0.2,
        industrial_land_score=80,
        zoning_compatibility_score=80,
        regulatory_stability_score=80,
        market_demand_score=80,
    )
    scores, flags = score_candidate(candidate, profile)
    final = compute_final_score(scores)
    assert 0 <= final <= 100


def test_all_scoring_profiles_have_valid_weights():
    errors = validate_all_profiles()
    assert len(errors) == 0, f"Weight validation errors: {errors}"


def test_land_score_flags():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-8",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    score, flags, quality = compute_land_score(candidate)
    assert quality is not None
    assert "ZONING_NOT_VERIFIED" in flags or "LAND_OWNERSHIP_UNKNOWN" in flags


def test_protected_area_proximity_adds_soft_constraint():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-pa-1",
        country="Test",
        region="Test",
        municipality="Test",
        lat=47.14,
        lon=9.55,
        geometry={"type": "Point", "coordinates": [9.55, 47.14]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_protected_area_km=0.5,
        nearest_substation_km=5.0,
        estimated_grid_capacity_mw=10,
        nearest_fiber_km=1.0,
        industrial_land_score=50,
    )
    from atlas.site_selection.exclusions import check_exclusions
    result = check_exclusions(candidate, profile)
    assert not result.excluded, "Protected area proximity should NOT trigger hard exclusion (centroid-only data)"
    assert any("protected area" in r.lower() for r in result.soft_constraints), "Should add soft constraint for protected area proximity"


def test_protected_area_proximity_flag_added():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-pa-2",
        country="Test",
        region="Test",
        municipality="Test",
        lat=47.14,
        lon=9.55,
        geometry={"type": "Point", "coordinates": [9.55, 47.14]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_protected_area_km=0.5,
    )
    # The flag is added by candidate_generator, but we verify the model supports it
    candidate.missing_data_flags.append("PROTECTED_AREA_PROXIMITY_OBSERVED")
    assert "PROTECTED_AREA_PROXIMITY_OBSERVED" in candidate.missing_data_flags


def test_protected_area_evidence_when_available():
    candidate = CandidateSite(
        candidate_site_id="test-pa-3",
        country="Test",
        region="Test",
        municipality="Test",
        lat=47.14,
        lon=9.55,
        geometry={"type": "Point", "coordinates": [9.55, 47.14]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_protected_area_km=1.2,
    )
    from atlas.site_selection.evidence import generate_evidence_summary
    summary = generate_evidence_summary(candidate)
    assert "protected area" in summary.lower()
    assert "1.2" in summary
    assert "OSM" in summary


def test_protected_area_proximity_none_when_no_data():
    candidate = CandidateSite(
        candidate_site_id="test-pa-4",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    from atlas.site_selection.evidence import generate_evidence_summary
    summary = generate_evidence_summary(candidate)
    assert "unknown" in summary.lower() or "no osm" in summary.lower()


def test_cable_score_with_proximity():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-cbl-1",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_cable_landing_km=2.0,
    )
    score, flags, quality = compute_cable_score(candidate)
    assert score > 80, f"Cable landing proximity should score high, got {score}"
    assert quality == "proxy"
    assert "CABLE_LANDING_UNKNOWN" not in flags


def test_cable_score_without_proximity():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-cbl-2",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    score, flags, quality = compute_cable_score(candidate)
    assert score < 50, f"Unknown cable landing should score low, got {score}"
    assert quality == "missing"
    assert "CABLE_LANDING_UNKNOWN" in flags


def test_cable_score_in_final_score():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-cbl-3",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_cable_landing_km=1.0,
        nearest_substation_km=5.0,
        estimated_grid_capacity_mw=10,
        nearest_fiber_km=0.5,
        industrial_land_score=50,
    )
    scores, flags = score_candidate(candidate, profile)
    assert scores.cable_score > 0
    assert candidate.cable_score > 0


def test_cable_landing_evidence():
    candidate = CandidateSite(
        candidate_site_id="test-cbl-4",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_cable_landing_km=5.0,
    )
    from atlas.site_selection.evidence import generate_evidence_summary
    summary = generate_evidence_summary(candidate)
    assert "cable landing" in summary.lower() or "submarine" in summary.lower()
    assert "5.0" in summary


def test_cable_landing_unknown_evidence():
    candidate = CandidateSite(
        candidate_site_id="test-cbl-5",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    from atlas.site_selection.evidence import generate_evidence_summary
    summary = generate_evidence_summary(candidate)
    assert "unknown" in summary.lower()


def test_proxy_confidence_penalty():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    candidate = CandidateSite(
        candidate_site_id="test-9",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("atlas.site_selection.scoring.compute_grid_score", lambda c, p: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_fiber_score", lambda c, p: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_land_score", lambda c: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_climate_score", lambda c: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_water_score", lambda c: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_regulatory_score", lambda c: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_market_score", lambda c: (80.0, [], "derived"))
        mp.setattr("atlas.site_selection.scoring.compute_incentive_score", lambda c: 80.0)

        from atlas.site_selection.confidence import compute_confidence_score
        score_candidate(candidate, profile)
        conf = compute_confidence_score(candidate)
        assert conf > 0, "Confidence should be calculable"


def test_grid_evidence_quality_derived():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-1", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        nearest_substation_km=1.0, estimated_grid_capacity_mw=10,
    )
    _, _, quality = compute_grid_score(c, profile)
    assert quality == "derived"


def test_grid_evidence_quality_proxy():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-2", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        nearest_substation_km=1.0,
    )
    _, _, quality = compute_grid_score(c, profile)
    assert quality == "proxy"


def test_grid_evidence_quality_missing():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-3", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_grid_score(c, profile)
    assert quality == "missing"


def test_fiber_evidence_quality_derived():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-4", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        nearest_fiber_km=0.5, fiber_proxy_level="facility",
    )
    _, _, quality = compute_fiber_score(c, profile)
    assert quality == "derived"


def test_fiber_evidence_quality_proxy():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-5", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        nearest_fiber_km=0.5,
    )
    _, _, quality = compute_fiber_score(c, profile)
    assert quality == "proxy"


def test_fiber_evidence_quality_missing():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-6", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_fiber_score(c, profile)
    assert quality == "missing"


def test_land_evidence_quality_derived():
    c = CandidateSite(
        candidate_site_id="t-eq-7", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        industrial_land_score=70, zoning_compatibility_score=70,
    )
    _, _, quality = compute_land_score(c)
    assert quality == "derived"


def test_land_evidence_quality_proxy():
    c = CandidateSite(
        candidate_site_id="t-eq-8", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        industrial_land_score=70,
    )
    _, _, quality = compute_land_score(c)
    assert quality == "proxy"


def test_land_evidence_quality_missing():
    c = CandidateSite(
        candidate_site_id="t-eq-9", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_land_score(c)
    assert quality == "missing"


def test_climate_evidence_quality_proxy():
    c = CandidateSite(
        candidate_site_id="t-eq-10", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        heat_risk_score=30,
    )
    _, _, quality = compute_climate_score(c)
    assert quality == "proxy"


def test_climate_evidence_quality_missing():
    c = CandidateSite(
        candidate_site_id="t-eq-11", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_climate_score(c)
    assert quality == "missing"


def test_water_evidence_quality_proxy():
    c = CandidateSite(
        candidate_site_id="t-eq-12", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        water_stress_score=40,
    )
    _, _, quality = compute_water_score(c)
    assert quality == "proxy"


def test_water_evidence_quality_missing():
    c = CandidateSite(
        candidate_site_id="t-eq-13", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_water_score(c)
    assert quality == "missing"


def test_regulatory_evidence_quality_derived():
    c = CandidateSite(
        candidate_site_id="t-eq-14", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        regulatory_stability_score=70,
    )
    _, _, quality = compute_regulatory_score(c)
    assert quality == "derived"


def test_regulatory_evidence_quality_missing():
    c = CandidateSite(
        candidate_site_id="t-eq-15", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_regulatory_score(c)
    assert quality == "missing"


def test_market_evidence_quality_proxy():
    c = CandidateSite(
        candidate_site_id="t-eq-16", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        market_demand_score=70,
    )
    _, _, quality = compute_market_score(c)
    assert quality == "proxy"


def test_market_evidence_quality_missing():
    c = CandidateSite(
        candidate_site_id="t-eq-17", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_market_score(c)
    assert quality == "missing"


def test_cable_evidence_quality_proxy():
    c = CandidateSite(
        candidate_site_id="t-eq-18", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        nearest_cable_landing_km=2.0,
    )
    _, _, quality = compute_cable_score(c)
    assert quality == "proxy"


def test_cable_evidence_quality_missing():
    c = CandidateSite(
        candidate_site_id="t-eq-19", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
    )
    _, _, quality = compute_cable_score(c)
    assert quality == "missing"


def test_score_candidate_sets_evidence_quality_on_candidate():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = CandidateSite(
        candidate_site_id="t-eq-20", country="T", region="T", municipality="T",
        lat=0, lon=0, geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2, compute_profile="regional_compute_5mw",
        nearest_substation_km=1.0, estimated_grid_capacity_mw=10,
        nearest_fiber_km=0.5, fiber_proxy_level="facility",
        industrial_land_score=70, zoning_compatibility_score=70,
        heat_risk_score=30, water_stress_score=40,
        regulatory_stability_score=70, market_demand_score=70,
        nearest_cable_landing_km=2.0,
    )
    score_candidate(c, profile)
    assert c.grid_evidence_quality == "derived"
    assert c.fiber_evidence_quality == "derived"
    assert c.land_evidence_quality == "derived"
    assert c.climate_evidence_quality == "proxy"
    assert c.water_evidence_quality == "proxy"
    assert c.regulatory_evidence_quality == "derived"
    assert c.market_evidence_quality == "proxy"
