"""Tests for atlas_core.json generation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_atlas_core import build_atlas_core
from scripts.build_web_map_data import build_web_data

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_atlas_core_minimal():
    """atlas_core.json contains no heavy coordinate arrays."""
    data = {
        "metadata": {
            "generated_at": "2026-01-01T00:00:00Z",
            "counts": {
                "power_plants_mapped": 100,
                "power_plants_total": 100,
                "power_plants_rejected": 0,
                "cables_mapped": 50,
                "cables_unmapped": 10,
                "cables_total": 60,
                "data_centers_mapped": 20,
                "data_centers_unmapped": 5,
                "data_centers_total": 25,
                "cable_geometry_source": "test",
                "cable_geometry_license_status": "to_verify",
                "cable_geometry_review_required": True,
                "data_center_source": "PeeringDB",
                "data_center_license_status": "test",
            },
            "sources": [
                {"key": "test_source", "name": "Test Source", "url": "", "license": "test"},
            ],
            "disclaimer": "Test disclaimer.",
        },
        "power_plants": [{"lat": 0, "lon": 0}],  # should not appear in core
        "cables": [],
        "data_centers": [],
    }

    core = build_atlas_core(data)

    # Core must not include heavy arrays
    assert "power_plants" not in core
    assert "cables" not in core
    assert "data_centers" not in core

    # Core must have required keys
    assert "generated_at" in core
    assert "architecture" in core
    assert "counts" in core
    assert "sources" in core
    assert "disclaimer" in core
    assert "tile_registry" in core
    assert "license_warnings" in core
    assert "data_gaps" in core

    # Counts
    assert core["counts"]["power_plants_mapped"] == 100
    assert core["counts"]["submarine_cables_mapped"] == 50
    assert core["counts"]["data_centers_mapped"] == 20

    # Sources preserve caller-provided entries and may append layer-specific
    # attribution discovered from metadata-only frontend files.
    assert any(source.get("key") == "test_source" for source in core["sources"])

    # Tile registry
    for key in ("power_plants", "submarine_cables", "data_centers"):
        assert key in core["tile_registry"]
        assert "url" in core["tile_registry"][key]
        assert "status" in core["tile_registry"][key]
        assert "layer_name" in core["tile_registry"][key]

    # License warnings
    assert len(core["license_warnings"]) >= 1

    # Serialization check — core must be small (< 50 KB)
    raw = json.dumps(core, ensure_ascii=False)
    assert len(raw) < 50 * 1024


def test_build_atlas_core_from_fixture(tmp_path, monkeypatch):
    """Build atlas_core from a minimal build_web_data run."""
    wri_csv = tmp_path / "wri.csv"
    wri_csv.write_text(
        "country,name,capacity_mw,latitude,longitude,primary_fuel\n"
        "US,OK,100,40,-75,Gas\n",
        encoding="utf-8",
    )
    cables_csv = tmp_path / "cables.csv"
    cables_csv.write_text("record_type,cable_system_name\n", encoding="utf-8")
    dcs_csv = tmp_path / "dcs.csv"
    dcs_csv.write_text("name,country\n", encoding="utf-8")

    monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
    monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
    monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
    monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
    monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")
    monkeypatch.setattr("scripts.build_web_map_data.PEERINGDB_COORDS_CSV", tmp_path / "nonexistent.csv")

    build_web_data(max_public_mb=5)

    output_path = tmp_path / "frontend_data" / "atlas_web_data.json"
    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)

    core = build_atlas_core(data)

    assert core["counts"]["power_plants_mapped"] == 1
    assert core["counts"]["submarine_cables_total"] == 0
    assert "sources" in core
    assert "tile_registry" in core
    assert "disclaimer" in core

    raw = json.dumps(core, ensure_ascii=False)
    assert len(raw) < 10 * 1024  # must be tiny


def test_build_atlas_core_accepts_remote_grid_tile_urls(monkeypatch):
    monkeypatch.setenv("POWER_LINES_PMTILES_URL", "https://tiles.example/power_lines.pmtiles")
    monkeypatch.setenv("SUBSTATIONS_PMTILES_URL", "https://tiles.example/substations.pmtiles")
    data = {
        "metadata": {
            "counts": {
                "power_plants_mapped": 1,
                "power_plants_total": 1,
                "power_plants_rejected": 0,
                "cables_mapped": 0,
                "cables_unmapped": 0,
                "cables_total": 0,
                "data_centers_mapped": 0,
                "data_centers_unmapped": 0,
                "data_centers_total": 0,
            },
            "sources": [],
            "disclaimer": "",
        }
    }

    core = build_atlas_core(data)

    assert core["tile_registry"]["power_lines"]["url"] == "pmtiles://https://tiles.example/power_lines.pmtiles"
    assert core["tile_registry"]["power_lines"]["deployment_mode"] == "remote"
    assert core["tile_registry"]["substations"]["url"] == "pmtiles://https://tiles.example/substations.pmtiles"
    assert core["tile_registry"]["substations"]["deployment_mode"] == "remote"


def test_build_atlas_core_derives_substation_bounds(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "power_lines.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": [], "metadata": {"total_features": 0}}),
        encoding="utf-8",
    )
    (data_dir / "substations.json").write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [10, 45]}, "properties": {}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [20, 35]}, "properties": {}},
            ],
            "metadata": {"total_features": 2},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.build_atlas_core.FRONTEND_DATA", data_dir)

    core = build_atlas_core({"metadata": {"counts": {}, "sources": [], "disclaimer": ""}})

    assert core["bounds"]["substations"] == {"minLon": 10.0, "minLat": 35.0, "maxLon": 20.0, "maxLat": 45.0}
