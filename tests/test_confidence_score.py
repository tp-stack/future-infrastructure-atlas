"""Tests for confidence scoring."""

import pytest
from atlas.site_selection.confidence import (
    compute_confidence_score,
    compute_data_completeness,
    compute_source_quality,
    is_human_review_required,
)
from atlas.site_selection.models import CandidateSite, MissingDataFlag
from atlas.site_selection.profiles import COMPUTE_PROFILES


def _make_candidate(**kwargs) -> CandidateSite:
    defaults = dict(
        candidate_site_id="test-conf",
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


def test_confidence_is_scored():
    c = _make_candidate()
    score = compute_confidence_score(c)
    assert 0 <= score <= 100


def test_data_completeness_empty():
    c = _make_candidate()
    completeness = compute_data_completeness(c)
    assert completeness < 50


def test_data_completeness_full():
    c = _make_candidate(
        nearest_substation_km=1,
        nearest_power_line_km=0.5,
        nearest_fiber_km=0.5,
        nearest_ixp_km=5,
        estimated_grid_capacity_mw=50,
        flood_risk_score=20,
        water_stress_score=30,
        regulatory_stability_score=70,
        market_demand_score=60,
        zoning_compatibility_score=80,
    )
    completeness = compute_data_completeness(c)
    assert completeness >= 80


def test_source_quality_penalized_by_flags():
    c = _make_candidate(
        missing_data_flags=[
            MissingDataFlag.GRID_CAPACITY_UNKNOWN.value,
            MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value,
        ]
    )
    quality = compute_source_quality(c)
    assert quality < 80


def test_human_review_high_score_low_confidence():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = _make_candidate(final_score=85, confidence_score=50)
    assert is_human_review_required(c, profile)


def test_human_review_large_profile_no_grid():
    profile = COMPUTE_PROFILES["sovereign_compute_campus_20mw"]
    c = _make_candidate(
        final_score=80,
        confidence_score=80,
        estimated_grid_capacity_mw=None,
        compute_profile="sovereign_compute_campus_20mw",
    )
    assert is_human_review_required(c, profile)


def test_human_review_zoning_not_verified():
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    c = _make_candidate(
        final_score=80,
        confidence_score=80,
        missing_data_flags=[MissingDataFlag.ZONING_NOT_VERIFIED.value],
    )
    assert is_human_review_required(c, profile)


def test_human_review_campus_water_unknown():
    profile = COMPUTE_PROFILES["sovereign_compute_campus_20mw"]
    c = _make_candidate(
        final_score=80,
        confidence_score=80,
        estimated_grid_capacity_mw=50,
        compute_profile="sovereign_compute_campus_20mw",
        missing_data_flags=[MissingDataFlag.WATER_ACCESS_UNKNOWN.value],
    )
    assert is_human_review_required(c, profile)
