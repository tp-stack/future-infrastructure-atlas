"""Tests for site selection API."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from atlas.site_selection.api import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_profiles(client):
    response = client.get("/v1/site-selection/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "compute_profiles" in data
    assert "scoring_profiles" in data
    assert len(data["compute_profiles"]) >= 4
    assert len(data["scoring_profiles"]) >= 2


def test_query_with_bbox(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 10,
        "include_excluded": False,
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert "count" in data
    assert "query_id" in data
    assert "metadata" in data
    assert "disclaimer" in data["metadata"]
    assert len(data["candidates"]) <= 10


def test_query_invalid_profile(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "nonexistent",
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 400


def test_query_invalid_area_type(client):
    payload = {
        "area": {"type": "circle", "coordinates": [0, 0, 10]},
        "profile": "regional_compute_5mw",
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 422 or response.status_code == 400


def test_score_point(client):
    payload = {
        "lat": 50.9,
        "lon": 5.9,
        "profile": "regional_compute_5mw",
    }
    response = client.post("/v1/site-selection/score-point", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "final_score" in data
    assert "confidence_score" in data
    assert "score_breakdown" in data
    assert "evidence_summary" in data


def test_candidate_detail_not_found(client):
    response = client.get("/v1/site-selection/candidate/nonexistent")
    assert response.status_code == 404


def test_export_report_ids_not_found(client):
    payload = {"candidate_ids": ["nonexistent-id"], "format": "json"}
    response = client.post("/v1/site-selection/export-report", json=payload)
    assert response.status_code == 404


def test_health(client):
    response = client.get("/v1/site-selection/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_invalid_bbox_structure(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6]},
        "profile": "regional_compute_5mw",
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 422


def test_query_response_contract(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "scoring_profile": "default",
        "limit": 5,
        "include_excluded": True,
    }
    response = client.post("/v1/site-selection/query", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert "candidates" in data
    assert "count" in data
    assert "query_id" in data
    assert "profile" in data
    assert "scoring_profile" in data
    assert "area" in data
    assert "metadata" in data
    if len(data["candidates"]) > 0:
        c = data["candidates"][0]
        assert "rank" in c
        assert "candidate_site_id" in c
        assert "final_score" in c
        assert "confidence_score" in c
        assert "grid_score" in c
        assert "fiber_score" in c
        assert "land_score" in c
        assert "climate_score" in c
        assert "regulatory_score" in c
        assert "market_score" in c
        assert "missing_data_flags" in c
        assert "human_review_required" in c
        assert "evidence_summary" in c
        assert "excluded" in c


def test_query_then_detail(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 3,
        "include_excluded": True,
    }
    query_resp = client.post("/v1/site-selection/query", json=payload)
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["count"] > 0
    candidate_id = query_data["candidates"][0]["candidate_site_id"]

    detail_resp = client.get(f"/v1/site-selection/candidate/{candidate_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["candidate_site_id"] == candidate_id
    assert "due_diligence_checklist" in detail_data
    assert "source_quality_notes" in detail_data
    assert "proxy_assumptions" in detail_data
    assert "disclaimer" in detail_data


def test_query_then_export_json(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 3,
        "include_excluded": True,
    }
    query_resp = client.post("/v1/site-selection/query", json=payload)
    query_data = query_resp.json()
    candidate_ids = [c["candidate_site_id"] for c in query_data["candidates"]]

    export_payload = {"candidate_ids": candidate_ids, "format": "json"}
    export_resp = client.post("/v1/site-selection/export-report", json=export_payload)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["report_type"] == "compute_site_selection"
    assert export_data["format"] == "json"
    assert export_data["candidate_count"] == len(candidate_ids)
    assert "disclaimer" in export_data


def test_query_then_export_csv(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 2,
        "include_excluded": True,
    }
    query_resp = client.post("/v1/site-selection/query", json=payload)
    query_data = query_resp.json()
    candidate_ids = [c["candidate_site_id"] for c in query_data["candidates"]]

    export_payload = {"candidate_ids": candidate_ids, "format": "csv"}
    export_resp = client.post("/v1/site-selection/export-report", json=export_payload)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["format"] == "csv"
    assert isinstance(export_data["content"], str)
    assert "DISCLAIMER" in export_data["content"]


def test_query_then_export_pdf_ready(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 2,
        "include_excluded": True,
    }
    query_resp = client.post("/v1/site-selection/query", json=payload)
    query_data = query_resp.json()
    candidate_ids = [c["candidate_site_id"] for c in query_data["candidates"]]

    export_payload = {"candidate_ids": candidate_ids, "format": "pdf_ready_json"}
    export_resp = client.post("/v1/site-selection/export-report", json=export_payload)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["format"] == "pdf_ready_json"
    assert "due_diligence_checklist" in export_data["content"]
    assert "disclaimer" in export_data
