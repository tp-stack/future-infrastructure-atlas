"""Tests for the exclusion engine."""

import pytest
from atlas.site_selection.exclusions import check_exclusions
from atlas.site_selection.models import CandidateSite
from atlas.site_selection.profiles import COMPUTE_PROFILES


def _make_candidate(**kwargs) -> CandidateSite:
    defaults = dict(
        candidate_site_id="test-x",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    defaults.update(kwargs)
    return CandidateSite(**defaults)


def test_no_exclusion_for_valid_site():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = _make_candidate(nearest_substation_km=2, nearest_fiber_km=1)
    result = check_exclusions(c, profile)
    assert not result.excluded
    assert len(result.hard_exclusions) == 0


def test_flood_risk_soft_constraint():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = _make_candidate(
        nearest_substation_km=2,
        nearest_fiber_km=1,
        flood_risk_score=90,
    )
    result = check_exclusions(c, profile)
    assert not result.excluded, "Proxy flood risk should not trigger hard exclusion"
    assert any("flood" in r.lower() for r in result.soft_constraints)


def test_seismic_risk_soft_constraint():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = _make_candidate(
        nearest_substation_km=2,
        nearest_fiber_km=1,
        seismic_risk_score=90,
    )
    result = check_exclusions(c, profile)
    assert not result.excluded, "Proxy seismic risk should not trigger hard exclusion"
    assert any("seismic" in r.lower() for r in result.soft_constraints)


def test_substation_distance_exclusion():
    profile = COMPUTE_PROFILES["edge_ai_node_1mw"]
    c = _make_candidate(nearest_substation_km=50, compute_profile="edge_ai_node_1mw")
    result = check_exclusions(c, profile)
    assert result.excluded
    assert any("substation" in r.lower() for r in result.hard_exclusions)


def test_no_power_infrastructure_exclusion():
    profile = COMPUTE_PROFILES["edge_ai_node_1mw"]
    c = _make_candidate(compute_profile="edge_ai_node_1mw")
    result = check_exclusions(c, profile)
    assert result.excluded
    assert any("power" in r.lower() for r in result.hard_exclusions)


def test_fiber_distance_exclusion():
    profile = COMPUTE_PROFILES["edge_ai_node_1mw"]
    c = _make_candidate(
        nearest_substation_km=1,
        nearest_fiber_km=100,
        compute_profile="edge_ai_node_1mw",
    )
    result = check_exclusions(c, profile)
    assert result.excluded
    assert any("fiber" in r.lower() for r in result.hard_exclusions)


def test_insufficient_area_exclusion():
    profile = COMPUTE_PROFILES["hyperscale_ai_campus_100mw"]
    c = _make_candidate(
        area_ha=1,
        nearest_substation_km=2,
        nearest_fiber_km=1,
        compute_profile="hyperscale_ai_campus_100mw",
        estimated_grid_capacity_mw=200,
    )
    result = check_exclusions(c, profile)
    assert result.excluded
    assert any("area" in r.lower() for r in result.hard_exclusions)


def test_soft_constraints_applied():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = _make_candidate(
        nearest_substation_km=2,
        nearest_fiber_km=1,
        water_stress_score=95,
        heat_risk_score=85,
        flood_risk_score=85,
        seismic_risk_score=90,
        wildfire_risk_score=95,
    )
    result = check_exclusions(c, profile)
    assert not result.excluded
    assert len(result.soft_constraints) >= 3
