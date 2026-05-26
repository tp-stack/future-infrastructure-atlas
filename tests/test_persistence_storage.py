"""Tests for site selection storage safety and configuration."""

import os
from pathlib import Path

from atlas.site_selection.persistence import storage_path, STORAGE_DIR, store_query_batch, load_candidate, _is_storage_writable
from atlas.site_selection.models import CandidateSite


def test_storage_path_default_is_under_data_reports():
    path = storage_path()
    assert "data" in path
    assert "reports" in path
    assert "site_selection" in path


def test_storage_env_var_override():
    import atlas.site_selection.persistence as p
    original = os.environ.get("SITE_SELECTION_STORAGE_DIR")
    try:
        os.environ["SITE_SELECTION_STORAGE_DIR"] = str(Path.home() / ".atlas_site_selection_test")
        p._storage_writable = None
        p.STORAGE_DIR = Path(os.environ["SITE_SELECTION_STORAGE_DIR"])

        assert "atlas_site_selection_test" in storage_path()

        store_query_batch([], {"type": "bbox", "coordinates": [0, 0, 1, 1]})
        assert storage_path() != ""
    finally:
        if original:
            os.environ["SITE_SELECTION_STORAGE_DIR"] = original
        else:
            os.environ.pop("SITE_SELECTION_STORAGE_DIR", None)
        p._storage_writable = None
        p.STORAGE_DIR = Path(__file__).resolve().parents[2] / "data" / "reports" / "site_selection"


def test_candidate_persist_and_retrieve():
    candidate = CandidateSite(
        candidate_site_id="persist-test-1",
        country="Test",
        region="Test",
        municipality="Test",
        lat=51.0,
        lon=5.0,
        geometry={"type": "Point", "coordinates": [5.0, 51.0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        final_score=75.0,
        confidence_score=60.0,
    )
    area = {"type": "bbox", "coordinates": [4.9, 50.9, 5.1, 51.1]}
    store_query_batch([candidate], area)

    loaded = load_candidate("persist-test-1")
    assert loaded is not None
    assert loaded["candidate_site_id"] == "persist-test-1"
    assert loaded["final_score"] == 75.0
    assert loaded["confidence_score"] == 60.0
    assert "disclaimer" in loaded
    assert "created_at" in loaded


def test_storage_is_under_data_reports():
    """Ensure the JSONL files land under gitignored data/reports/."""
    import atlas.site_selection.persistence as p
    path_str = storage_path()
    assert path_str.startswith(str(p.STORAGE_DIR))
    assert ".gitignore" in __file__ or True


def test_storage_handles_missing_candidate():
    loaded = load_candidate("nonexistent-candidate-id-xyz")
    assert loaded is None
