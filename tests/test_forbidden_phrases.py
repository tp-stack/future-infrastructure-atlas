"""Tests that no forbidden phrases appear in any site selection output."""

import pytest
from atlas.site_selection.api import FINAL_OUTPUT_DISCLAIMER, SOURCE_QUALITY_NOTES
from atlas.site_selection.evidence import generate_evidence_summary
from atlas.site_selection.models import CandidateSite
from atlas.site_selection.report_builder import DISCLAIMER_TEXT, _due_diligence_checklist

FORBIDDEN_PHRASES = [
    "approved site",
    "guaranteed buildable",
    "certified location",
    "legally compliant location",
    "grid-approved",
    "investment-ready",
    "definitive site selection",
    "permitted site",
]


def _check_text(text: str) -> list[str]:
    found = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text.lower():
            found.append(phrase)
    return found


def test_disclaimer_has_no_forbidden_phrases():
    found = _check_text(FINAL_OUTPUT_DISCLAIMER)
    assert len(found) == 0, f"Found forbidden phrases in disclaimer: {found}"


def test_report_builder_disclaimer_has_no_forbidden_phrases():
    found = _check_text(DISCLAIMER_TEXT)
    assert len(found) == 0, f"Found forbidden phrases in report DISCLAIMER_TEXT: {found}"


def test_source_quality_notes_have_no_forbidden_phrases():
    for flag, note in SOURCE_QUALITY_NOTES.items():
        found = _check_text(note)
        assert len(found) == 0, f"Found forbidden phrases in source note for {flag}: {found}"


def test_due_diligence_checklist_has_no_forbidden_phrases():
    for item in _due_diligence_checklist():
        found = _check_text(item)
        assert len(found) == 0, f"Found forbidden phrases in checklist item: {found}"


def test_evidence_summary_has_no_forbidden_phrases():
    candidate = CandidateSite(
        candidate_site_id="test-fp",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    summary = generate_evidence_summary(candidate)
    found = _check_text(summary)
    assert len(found) == 0, f"Found forbidden phrases in evidence summary: {found}"


COUNTRY_LEVEL_FLAGS = [
    "GRID_CAPACITY_UNKNOWN",
    "FIBER_AVAILABILITY_UNKNOWN",
    "ZONING_NOT_VERIFIED",
    "LAND_OWNERSHIP_UNKNOWN",
    "WATER_ACCESS_UNKNOWN",
    "CLIMATE_RISK_PROXY_ONLY",
    "REGULATORY_SCORE_COUNTRY_LEVEL_ONLY",
    "MARKET_DEMAND_PROXY_ONLY",
    "ADMIN_GEOCODING_NOT_AVAILABLE",
]


def test_all_missing_data_flags_have_source_notes():
    for flag in COUNTRY_LEVEL_FLAGS:
        assert flag in SOURCE_QUALITY_NOTES, f"Missing source quality note for flag: {flag}"
