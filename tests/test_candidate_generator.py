"""Tests for the candidate generator."""

import pytest
from atlas.site_selection.candidate_generator import (
    generate_candidates_from_bbox,
    generate_candidates_from_polygon,
    _generate_grid_cells,
    _area_ha_from_bbox,
)


def test_generate_grid_cells():
    bbox = (0.0, 0.0, 1.0, 1.0)
    cells = _generate_grid_cells(bbox, 0.5)
    assert len(cells) == 4


def test_generate_grid_cells_small():
    bbox = (0.0, 0.0, 0.1, 0.1)
    cells = _generate_grid_cells(bbox, 0.05)
    assert len(cells) == 4


def test_area_ha_from_bbox():
    area = _area_ha_from_bbox((0, 0, 1, 1), 0)
    assert area > 0


def test_generate_candidates_from_bbox_returns_ranked():
    bbox = (5.5, 50.6, 6.4, 51.2)
    candidates, query_id = generate_candidates_from_bbox(
        bbox=bbox,
        profile_key="regional_compute_5mw",
        limit=10,
        include_excluded=False,
    )
    assert len(candidates) <= 10
    assert len(query_id) > 0
    assert query_id.startswith("q-")
    if len(candidates) >= 2:
        assert candidates[0].final_score >= candidates[1].final_score


def test_generate_candidates_have_scores():
    bbox = (5.5, 50.6, 6.4, 51.2)
    candidates, query_id = generate_candidates_from_bbox(
        bbox=bbox,
        profile_key="regional_compute_5mw",
        limit=5,
        include_excluded=False,
    )
    for c in candidates:
        assert c.final_score >= 0
        assert c.confidence_score >= 0
        assert c.candidate_site_id is not None


def test_generate_candidates_have_evidence():
    bbox = (5.5, 50.6, 6.4, 51.2)
    candidates, query_id = generate_candidates_from_bbox(
        bbox=bbox,
        profile_key="regional_compute_5mw",
        limit=3,
        include_excluded=False,
    )
    for c in candidates:
        assert len(c.evidence_summary) > 0


def test_generate_candidates_from_polygon():
    polygon = [[[5.5, 50.6], [6.4, 50.6], [6.4, 51.2], [5.5, 51.2], [5.5, 50.6]]]
    candidates, query_id = generate_candidates_from_polygon(
        polygon=polygon,
        profile_key="regional_compute_5mw",
        limit=5,
        include_excluded=True,
    )
    assert len(candidates) > 0
    assert len(query_id) > 0


def test_unknown_profile_raises():
    bbox = (5.5, 50.6, 6.4, 51.2)
    with pytest.raises(ValueError, match="Unknown compute profile"):
        generate_candidates_from_bbox(bbox=bbox, profile_key="nonexistent")
