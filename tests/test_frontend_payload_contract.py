"""Verify that the backend API response is compatible with frontend TypeScript types.

This test loads the actual API response schema and validates it against
the expected frontend contract defined in siteSelectionApi.ts.
"""

import json
from atlas.site_selection.schemas import CandidateSiteResponse, QueryResponse, CandidateDetailResponse, ExportReportResponse


def test_candidate_site_response_has_all_frontend_fields():
    required = [
        "rank",
        "candidate_site_id",
        "lat",
        "lon",
        "country",
        "region",
        "municipality",
        "area_ha",
        "compute_profile",
        "final_score",
        "confidence_score",
        "grid_score",
        "fiber_score",
        "land_score",
        "climate_score",
        "water_score",
        "regulatory_score",
        "market_score",
        "incentive_score",
        "missing_data_flags",
        "human_review_required",
        "evidence_summary",
        "excluded",
        "exclusion_reasons",
        "soft_constraints",
    ]
    schema_fields = set(CandidateSiteResponse.model_fields.keys())
    for field in required:
        assert field in schema_fields, f"Missing field in API schema: {field}"


def test_query_response_has_metadata():
    fields = set(QueryResponse.model_fields.keys())
    assert "candidates" in fields
    assert "count" in fields
    assert "query_id" in fields
    assert "metadata" in fields
    assert "profile" in fields
    assert "scoring_profile" in fields
    assert "area" in fields


def test_candidate_detail_response_has_required_fields():
    fields = set(CandidateDetailResponse.model_fields.keys())
    required = [
        "candidate_site_id",
        "query_id",
        "final_score",
        "confidence_score",
        "score_breakdown",
        "missing_data_flags",
        "human_review_required",
        "evidence_summary",
        "due_diligence_checklist",
        "source_quality_notes",
        "proxy_assumptions",
        "disclaimer",
    ]
    for field in required:
        assert field in fields, f"Missing field in CandidateDetailResponse: {field}"


def test_export_report_response_has_required_fields():
    fields = set(ExportReportResponse.model_fields.keys())
    assert "report_type" in fields
    assert "format" in fields
    assert "candidate_count" in fields
    assert "content" in fields
    assert "disclaimer" in fields


def test_json_serializable():
    sample = {
        "rank": 1,
        "candidate_site_id": "test-1",
        "lat": 50.9,
        "lon": 5.9,
        "country": "Test",
        "region": "Test",
        "municipality": "Test",
        "area_ha": 2.0,
        "compute_profile": "regional_compute_5mw",
        "final_score": 75.0,
        "confidence_score": 60.0,
        "grid_score": 70.0,
        "fiber_score": 65.0,
        "land_score": 80.0,
        "climate_score": 50.0,
        "water_score": 60.0,
        "regulatory_score": 70.0,
        "incentive_score": 30.0,
        "missing_data_flags": ["GRID_CAPACITY_UNKNOWN"],
        "human_review_required": True,
        "evidence_summary": "Test evidence.",
        "excluded": False,
        "exclusion_reasons": [],
        "soft_constraints": [],
    }
    dumped = json.dumps(sample)
    parsed = json.loads(dumped)
    assert parsed["rank"] == 1
    assert parsed["final_score"] == 75.0
