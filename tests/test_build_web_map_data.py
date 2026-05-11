from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_web_map_data import (
    FRONTEND_DATA,
    PROCESSED_WEB,
    WRI_CSV,
    _find_country_col,
    _normalize_fuel,
    _read_cables,
    _read_datacenters,
    _read_wri,
    _valid_lat,
    _valid_lng,
    build_web_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


def test_find_country_col_normal():
    fieldnames = ["name", "country", "fuel_type", "capacity_mw", "latitude", "longitude"]
    assert _find_country_col(fieldnames) == "country"


def test_find_country_col_weird():
    fieldnames = ["  WRI Global Power Plant Databasecountry", "country_long", "name"]
    result = _find_country_col(fieldnames)
    assert "country" in result.lower()


def test_valid_lat_accepts_good():
    assert _valid_lat("40.0") is True
    assert _valid_lat("-33.86") is True
    assert _valid_lat("90.0") is True
    assert _valid_lat("-90.0") is True


def test_valid_lat_rejects_bad():
    assert _valid_lat("") is False
    assert _valid_lat("999.0") is False
    assert _valid_lat("abc") is False
    assert _valid_lat("91.0") is False
    assert _valid_lat("-91.0") is False


def test_valid_lng_accepts_good():
    assert _valid_lng("0.0") is True
    assert _valid_lng("180.0") is True
    assert _valid_lng("-180.0") is True
    assert _valid_lng("12.4924") is True


def test_valid_lng_rejects_bad():
    assert _valid_lng("") is False
    assert _valid_lng("181.0") is False
    assert _valid_lng("-181.0") is False
    assert _valid_lng("abc") is False


def test_normalize_fuel():
    assert _normalize_fuel("Natural Gas") == "Natural Gas"
    assert _normalize_fuel("natural gas") == "Natural Gas"
    assert _normalize_fuel("Solar") == "Solar"
    assert _normalize_fuel("solar") == "Solar"
    assert _normalize_fuel("") == "Other"
    assert _normalize_fuel("  ") == "Other"
    assert _normalize_fuel("UnknownFuel") == "UnknownFuel"


def test_read_wri_from_fixture():
    fixture = FIXTURES / "sample_wri_power_plants.csv"
    records, rejected = _read_wri(fixture)
    assert len(records) == 2
    assert rejected == 1
    assert records[0]["n"] == "Plant Alpha"
    assert records[1]["n"] == "Plant Beta"
    assert records[0]["f"] == "Natural Gas"
    assert records[1]["f"] == "Solar"


def test_read_wri_missing_file():
    with pytest.raises(FileNotFoundError):
        _read_wri(Path("nonexistent.csv"))


def test_read_cables_empty_fixture(tmp_path):
    csv_path = tmp_path / "cables.csv"
    csv_path.write_text(
        "record_type,cable_system_name,operators,landing_points,segment_endpoints\n",
        encoding="utf-8",
    )
    records, rejected = _read_cables(csv_path)
    assert records == []
    assert rejected == 0


def test_read_datacenters_empty_fixture(tmp_path):
    csv_path = tmp_path / "dc.csv"
    csv_path.write_text(
        "name,country,owner,address,current_power_mw\n",
        encoding="utf-8",
    )
    records, rejected = _read_datacenters(csv_path)
    assert records == []
    assert rejected == 0


def test_datacenter_missing_file():
    with pytest.raises(FileNotFoundError):
        _read_datacenters(Path("nonexistent.csv"))


def test_cable_missing_file():
    with pytest.raises(FileNotFoundError):
        _read_cables(Path("nonexistent.csv"))


def test_build_web_data_from_fixtures(tmp_path, monkeypatch):
    wri_csv = tmp_path / "wri.csv"
    wri_csv.write_text(
        "country,country_long,name,gppd_idnr,capacity_mw,latitude,longitude,primary_fuel\n"
        "US,United States,Plant A,GEN001,100.0,40.0,-75.0,Natural Gas\n"
        "IT,Italy,Plant B,GEN002,50.0,41.8902,12.4924,Solar\n"
        "DE,Germany,Plant C,GEN003,200.0,999.0,10.0,Wind\n",
        encoding="utf-8",
    )
    cables_csv = tmp_path / "cables.csv"
    cables_csv.write_text(
        "record_type,cable_system_name,operators,landing_points,segment_endpoints\n"
        "segment,Alpha Cable,OpCo,CityA;CityB,Port1;Port2\n",
        encoding="utf-8",
    )
    dcs_csv = tmp_path / "dcs.csv"
    dcs_csv.write_text(
        "name,country,owner,address,current_power_mw\n"
        "DC Alpha,USA,OpCorp,\"123 Main St, City\",500\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "scripts.build_web_map_data.WRI_CSV", wri_csv
    )
    monkeypatch.setattr(
        "scripts.build_web_map_data.CABLES_CSV", cables_csv
    )
    monkeypatch.setattr(
        "scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv
    )
    monkeypatch.setattr(
        "scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data"
    )
    monkeypatch.setattr(
        "scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web"
    )

    build_web_data(max_public_mb=5)

    output = tmp_path / "frontend_data" / "atlas_web_data.json"
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))

    assert "metadata" in data
    assert "power_plants" in data
    assert "cables" in data
    assert "data_centers" in data

    assert len(data["power_plants"]) == 2
    assert data["metadata"]["counts"]["power_plants_rejected"] == 1
    assert data["metadata"]["counts"]["power_plants_total"] == 3
    assert data["metadata"]["counts"]["submarine_cables_unmapped"] == 1
    assert data["metadata"]["counts"]["data_centers_unmapped"] == 1
    assert data["metadata"]["counts"]["cables_unmapped"] == 1
    assert data["metadata"]["counts"]["cables_mapped"] == 0
    assert data["metadata"]["counts"]["cables_total"] == 1

    assert len(data["metadata"]["unmapped"]["submarine_cables"]) == 1
    assert data["metadata"]["unmapped"]["submarine_cables"][0]["n"] == "Alpha Cable"


def test_cap_enforced(tmp_path, monkeypatch):
    wri_csv = tmp_path / "wri.csv"
    lines = ["country,country_long,name,gppd_idnr,capacity_mw,latitude,longitude,primary_fuel"]
    for i in range(10000):
        lines.append(f"US,United States,Plant {i},GEN{i},100.0,40.0,-75.0,Natural Gas")
    wri_csv.write_text("\n".join(lines), encoding="utf-8")

    cables_csv = tmp_path / "cables.csv"
    cables_csv.write_text("record_type,cable_system_name\n", encoding="utf-8")
    dcs_csv = tmp_path / "dcs.csv"
    dcs_csv.write_text("name,country\n", encoding="utf-8")

    monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
    monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
    monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
    monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
    monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")

    success = build_web_data(max_public_mb=0.001)
    assert success is False

    frontend_out = tmp_path / "frontend_data" / "atlas_web_data.json"
    processed_out = tmp_path / "processed_web" / "atlas_web_data.json"
    assert not frontend_out.exists()
    assert processed_out.exists()


def test_raw_csv_not_in_frontend(tmp_path, monkeypatch):
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

    build_web_data(max_public_mb=5)

    frontend_files = list((tmp_path / "frontend_data").iterdir())
    csv_in_frontend = [f for f in frontend_files if f.suffix == ".csv"]
    assert csv_in_frontend == []


def test_power_plant_rejected_invalid_coords(tmp_path, monkeypatch):
    wri_csv = tmp_path / "wri.csv"
    wri_csv.write_text(
        "country,country_long,name,gppd_idnr,capacity_mw,latitude,longitude,primary_fuel\n"
        "US,United States,Good Plant,GEN001,100.0,40.0,-75.0,Gas\n"
        "DE,Germany,Bad Lat,GEN002,50.0,999.0,10.0,Wind\n"
        "FR,France,Bad Lon,GEN003,50.0,45.0,200.0,Solar\n"
        "IT,Italy,Empty Lat,GEN004,50.0,,10.0,Gas\n",
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

    build_web_data(max_public_mb=5)
    output = tmp_path / "frontend_data" / "atlas_web_data.json"
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data["power_plants"]) == 1
    assert data["power_plants"][0]["n"] == "Good Plant"
    assert data["metadata"]["counts"]["power_plants_rejected"] == 3


def test_build_metadata_has_generated_at(tmp_path, monkeypatch):
    wri_csv = tmp_path / "wri.csv"
    wri_csv.write_text("country,name,capacity_mw,latitude,longitude,primary_fuel\nUS,OK,100,40,-75,Gas\n", encoding="utf-8")
    cables_csv = tmp_path / "cables.csv"
    cables_csv.write_text("record_type,cable_system_name\n", encoding="utf-8")
    dcs_csv = tmp_path / "dcs.csv"
    dcs_csv.write_text("name,country\n", encoding="utf-8")

    monkeypatch.setattr("scripts.build_web_map_data.WRI_CSV", wri_csv)
    monkeypatch.setattr("scripts.build_web_map_data.CABLES_CSV", cables_csv)
    monkeypatch.setattr("scripts.build_web_map_data.DATACENTERS_CSV", dcs_csv)
    monkeypatch.setattr("scripts.build_web_map_data.FRONTEND_DATA", tmp_path / "frontend_data")
    monkeypatch.setattr("scripts.build_web_map_data.PROCESSED_WEB", tmp_path / "processed_web")

    build_web_data(max_public_mb=5)
    output = tmp_path / "frontend_data" / "atlas_web_data.json"
    data = json.loads(output.read_text(encoding="utf-8"))
    assert "generated_at" in data["metadata"]
    assert data["metadata"]["generated_at"].endswith("Z")
    assert len(data["metadata"]["sources"]) == 3
    assert "disclaimer" in data["metadata"]
