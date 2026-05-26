"""Tests for API safety: limits, error handling, stack traces, format rejection."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from atlas.site_selection.api import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_query_limit_is_respected(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 200,
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 422


def test_query_max_limit_capped(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "regional_compute_5mw",
        "limit": 100,
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["candidates"]) <= 100


def test_export_report_rejects_invalid_format(client):
    payload = {"candidate_ids": ["abc"], "format": "xml"}
    response = client.post("/v1/site-selection/export-report", json=payload)
    assert response.status_code == 422


def test_export_report_unknown_candidates_returns_404(client):
    payload = {"candidate_ids": ["nonexistent-id"], "format": "json"}
    response = client.post("/v1/site-selection/export-report", json=payload)
    assert response.status_code == 404


def test_score_point_out_of_bounds(client):
    payload = {"lat": 200, "lon": 5.9, "profile": "regional_compute_5mw"}
    response = client.post("/v1/site-selection/score-point", json=payload)
    assert response.status_code == 422


def test_query_empty_profile(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "",
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 400


def test_api_returns_json_not_html(client):
    response = client.get("/v1/site-selection/nonexistent-route")
    assert response.status_code == 404
    content_type = response.headers.get("content-type", "")
    assert "json" in content_type


def test_error_response_has_detail(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "nonexistent",
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


def test_error_does_not_contain_stack_trace(client):
    client_no_debug = TestClient(FastAPI())
    client_no_debug.app.include_router(router)
    payload = {
        "area": {"type": "bbox", "coordinates": [5.5, 50.6, 6.4, 51.2]},
        "profile": "nonexistent",
    }
    response = client_no_debug.post("/v1/site-selection/query", json=payload)
    body = response.text.lower()
    assert "traceback" not in body
    assert "file \"" not in body
    assert "line " not in body


def test_query_handles_empty_area(client):
    payload = {
        "area": {"type": "bbox", "coordinates": [0, 0, 0.01, 0.01]},
        "profile": "regional_compute_5mw",
        "limit": 5,
    }
    response = client.post("/v1/site-selection/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["candidates"], list)
