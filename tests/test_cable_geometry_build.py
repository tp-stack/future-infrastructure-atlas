from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_web_map_data import (
    _load_cable_geometry_csv,
    _load_cable_geom_lookup,
    _read_cables,
    _read_datacenters,
    _read_wri,
    build_web_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


class TestLoadCableGeometryCsv:
    def test_loads_valid_csv(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text(
            'cable_name,geometry_type,geometry_json,source_name,source_license,license_review_required,geometry_precision,confidence,source_url\n'
            'Cable A,LineString,"{""type"":""LineString"",""coordinates"":[[0,0],[1,1]]}",TestSrc,to_verify,true,generalized,0.65,\n'
            'Cable B,MultiLineString,"{""type"":""MultiLineString"",""coordinates"":[[[0,0],[1,1]],[[2,2],[3,3]]]}",TestSrc,to_verify,true,generalized,0.65,\n',
            encoding="utf-8",
        )
        lookup = _load_cable_geometry_csv(csv)
        assert "cable_a" in lookup
        assert "cable_b" in lookup
        assert len(lookup["cable_a"]["geometry"]) == 2
        assert len(lookup["cable_b"]["geometry"]) == 2

    def test_skips_empty_name(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text(
            'cable_name,geometry_type,geometry_json\n'
            ',LineString,"{""type"":""LineString"",""coordinates"":[[0,0],[1,1]]}"\n',
            encoding="utf-8",
        )
        lookup = _load_cable_geometry_csv(csv)
        assert lookup == {}

    def test_skips_invalid_geometry_json(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text(
            'cable_name,geometry_type,geometry_json\n'
            'Cable A,LineString,not-json\n',
            encoding="utf-8",
        )
        lookup = _load_cable_geometry_csv(csv)
        assert lookup == {}

    def test_skips_bad_coords(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text(
            'cable_name,geometry_type,geometry_json\n'
            'Cable A,LineString,"{""type"":""LineString"",""coordinates"":[[200,0],[1,1]]}"\n',
            encoding="utf-8",
        )
        lookup = _load_cable_geometry_csv(csv)
        assert lookup == {}

    def test_returns_empty_on_missing_file(self, tmp_path):
        lookup = _load_cable_geometry_csv(tmp_path / "nonexistent.csv")
        assert lookup == {}

    def test_fixture_csv_loads(self):
        path = FIXTURES / "sample_cable_geometries.csv"
        lookup = _load_cable_geometry_csv(path)
        assert "test_cable_alpha" in lookup
        assert "test_cable_beta" in lookup
        assert lookup["test_cable_alpha"]["geometry_type"] == "MultiLineString"

    def test_merges_duplicate_cable_geometry_rows(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text(
            'cable_name,geometry_type,geometry_json,source_name,source_license,license_review_required,geometry_precision,confidence,source_url\n'
            'Cable A,LineString,"{""type"":""LineString"",""coordinates"":[[0,0],[1,1]]}",TestSrc,to_verify,true,generalized,0.65,\n'
            'Cable A,LineString,"{""type"":""LineString"",""coordinates"":[[2,2],[3,3]]}",TestSrc,to_verify,true,generalized,0.65,\n',
            encoding="utf-8",
        )
        lookup = _load_cable_geometry_csv(csv)

        assert lookup["cable_a"]["geometry_type"] == "MultiLineString"
        assert len(lookup["cable_a"]["geometry"]) == 2


class TestBuildWithCableGeometryCsv:
    def test_build_with_csv(self, tmp_path, monkeypatch):
        wri_csv = tmp_path / "wri.csv"
        wri_csv.write_text(
            "country,country_long,name,gppd_idnr,capacity_mw,latitude,longitude,primary_fuel\n"
            "US,United States,Plant A,GEN001,100.0,40.0,-75.0,Natural Gas\n",
            encoding="utf-8",
        )
        cables_csv = tmp_path / "cables.csv"
        cables_csv.write_text(
            "record_type,cable_system_name,operators,landing_points,segment_endpoints\n"
            "segment,Test Cable Alpha,OpCo,CityA;CityB,Port1;Port2\n"
            "segment,Test Cable Beta,NetCo,PortX;PortY,Port3;Port4\n",
            encoding="utf-8",
        )
        dcs_csv = tmp_path / "dcs.csv"
        dcs_csv.write_text("name,country\n", encoding="utf-8")

        geom_csv = tmp_path / "geom.csv"
        geom_csv.write_text(
            'cable_name,geometry_type,geometry_json,source_name,source_license,license_review_required,geometry_precision,confidence,source_url\n'
            'Test Cable Alpha,LineString,"{""type"":""LineString"",""coordinates"":[[0,0],[1,1],[2,2]]}",KMCD,to_verify,true,generalized,0.65,\n',
            encoding="utf-8",
        )

        monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
        monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
        monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
        monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
        monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")

        success = build_web_data(
            max_public_mb=5,
            cable_geometry_csv_path=geom_csv,
            allow_license_review=True,
        )
        assert success is True

        output = tmp_path / "frontend_data" / "atlas_web_data.json"
        assert output.exists()
        data = json.loads(output.read_text(encoding="utf-8"))

        assert len(data["cables"]) == 2
        mapped = [c for c in data["cables"] if c.get("mapped_status") == "mapped"]
        assert len(mapped) == 1
        assert mapped[0]["n"] == "Test Cable Alpha"
        assert len(mapped[0]["geometry"]) == 3
        assert data["metadata"]["counts"]["cable_geometry_source"] == "KMCD Internet Infrastructure Map"
        assert data["metadata"]["counts"]["cable_geometry_review_required"] is True

    def test_build_appends_geometry_only_cables(self, tmp_path, monkeypatch):
        wri_csv = tmp_path / "wri.csv"
        wri_csv.write_text(
            "country,name,capacity_mw,latitude,longitude,primary_fuel\nUS,OK,100,40,-75,Gas\n",
            encoding="utf-8",
        )
        cables_csv = tmp_path / "cables.csv"
        cables_csv.write_text(
            "record_type,cable_system_name,operators,landing_points,segment_endpoints\n"
            "segment,Matched Cable,OpCo,CityA;CityB,Port1;Port2\n",
            encoding="utf-8",
        )
        dcs_csv = tmp_path / "dcs.csv"
        dcs_csv.write_text("name,country\n", encoding="utf-8")
        geom_csv = tmp_path / "geom.csv"
        geom_csv.write_text(
            'cable_name,geometry_type,geometry_json,source_name,source_license,license_review_required,geometry_precision,confidence,source_url\n'
            'Matched Cable,LineString,"{""type"":""LineString"",""coordinates"":[[0,0],[1,1]]}",KMCD,to_verify,true,generalized,0.65,\n'
            'Geometry Only Cable,LineString,"{""type"":""LineString"",""coordinates"":[[2,2],[3,3]]}",KMCD,to_verify,true,generalized,0.65,\n',
            encoding="utf-8",
        )

        monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
        monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
        monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
        monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
        monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")

        success = build_web_data(
            max_public_mb=5,
            cable_geometry_csv_path=geom_csv,
            allow_license_review=True,
        )
        assert success is True

        data = json.loads((tmp_path / "frontend_data" / "atlas_web_data.json").read_text(encoding="utf-8"))
        assert data["metadata"]["counts"]["cables_total"] == 2
        assert data["metadata"]["counts"]["cables_mapped"] == 2
        assert {c["n"] for c in data["cables"]} == {"Matched Cable", "Geometry Only Cable"}

    def test_rejects_without_allow_license_review(self, tmp_path, monkeypatch):
        wri_csv = tmp_path / "wri.csv"
        wri_csv.write_text(
            "country,name,capacity_mw,latitude,longitude,primary_fuel\nUS,OK,100,40,-75,Gas\n",
            encoding="utf-8",
        )
        cables_csv = tmp_path / "cables.csv"
        cables_csv.write_text("record_type,cable_system_name\n", encoding="utf-8")
        dcs_csv = tmp_path / "dcs.csv"
        dcs_csv.write_text("name,country\n", encoding="utf-8")

        geom_csv = tmp_path / "geom.csv"
        geom_csv.write_text(
            'cable_name,geometry_type,geometry_json,source_license,license_review_required\n'
            'Cable A,LineString,"{""type"":""LineString"",""coordinates"":[[0,0],[1,1]]}",to_verify,true\n',
            encoding="utf-8",
        )

        monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
        monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
        monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
        monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
        monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")

        with pytest.raises(SystemExit):
            build_web_data(
                max_public_mb=5,
                cable_geometry_csv_path=geom_csv,
                allow_license_review=False,
            )

    def test_no_geom_csv_falls_back(self, tmp_path, monkeypatch):
        wri_csv = tmp_path / "wri.csv"
        wri_csv.write_text(
            "country,name,capacity_mw,latitude,longitude,primary_fuel\nUS,OK,100,40,-75,Gas\n",
            encoding="utf-8",
        )
        cables_csv = tmp_path / "cables.csv"
        cables_csv.write_text("record_type,cable_system_name\nAlpha Cable,\n", encoding="utf-8")
        dcs_csv = tmp_path / "dcs.csv"
        dcs_csv.write_text("name,country\n", encoding="utf-8")

        monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
        monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
        monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
        monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
        monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")

        success = build_web_data(max_public_mb=5)
        assert success is True

        output = tmp_path / "frontend_data" / "atlas_web_data.json"
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["metadata"]["counts"]["cable_geometry_source"] == "legacy_lookup"


class TestFetchAndBuildScript:
    def test_fixture_geojson_to_csv(self, tmp_path):
        import subprocess
        import sys
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "fetch_and_build_cable_geometry_csv.py"),
                "--input-geojson",
                str(FIXTURES / "sample_cable_geometries.geojson"),
                "--output-csv",
                str(tmp_path / "out.csv"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "Valid features: 2" in result.stdout
        assert "Invalid/rejected: 2" in result.stdout

        out_csv = tmp_path / "out.csv"
        assert out_csv.exists()

        import csv
        with open(out_csv, newline="", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 2
        names = {r["cable_name"] for r in reader}
        assert "Test Cable Alpha" in names
        assert "Test Cable Beta" in names

        for row in reader:
            geom = json.loads(row["geometry_json"])
            assert geom["type"] in ("LineString", "MultiLineString")
            assert row["source_license"] == "to_verify"
            assert row["license_review_required"] == "true"
            assert row["geometry_precision"] == "generalized_public_geometry"
            assert row["confidence"] == "0.65"
