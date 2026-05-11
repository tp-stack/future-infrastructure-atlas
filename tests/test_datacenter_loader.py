from __future__ import annotations

from pathlib import Path

from atlas.ingestion.datacenter_loader import (
    _field,
    _get_dc_city,
    _get_dc_country,
    _get_dc_name,
    _get_dc_name_from_row,
    _get_dc_operator,
    _parse_mw,
    load_datacenters_from_csv,
    load_datacenters_from_geojson,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


class TestGetDcName:
    def test_from_name_field(self):
        assert _get_dc_name({"name": "DC A"}) == "DC A"

    def test_from_facility_name_field(self):
        assert _get_dc_name({"facility_name": "DC B"}) == "DC B"

    def test_from_title_field(self):
        assert _get_dc_name({"title": "DC C"}) == "DC C"

    def test_returns_empty_when_none(self):
        assert _get_dc_name({}) == ""
        assert _get_dc_name({"name": ""}) == ""
        assert _get_dc_name({"name": "  "}) == ""


class TestGetDcNameFromRow:
    def test_from_name_field(self):
        assert _get_dc_name_from_row({"name": "DC A"}) == "DC A"

    def test_from_facility_name_field(self):
        assert _get_dc_name_from_row({"facility_name": "DC B"}) == "DC B"

    def test_from_title_field(self):
        assert _get_dc_name_from_row({"title": "DC C"}) == "DC C"

    def test_returns_empty_when_none(self):
        assert _get_dc_name_from_row({}) == ""
        assert _get_dc_name_from_row({"name": ""}) == ""


class TestGetDcOperator:
    def test_from_operator(self):
        assert _get_dc_operator({"operator": "OpCo"}) == "OpCo"

    def test_from_owner(self):
        assert _get_dc_operator({"owner": "OwnCo"}) == "OwnCo"

    def test_from_op(self):
        assert _get_dc_operator({"op": "Op"}) == "Op"

    def test_returns_empty(self):
        assert _get_dc_operator({}) == ""


class TestGetDcCountry:
    def test_from_country(self):
        assert _get_dc_country({"country": "US"}) == "US"

    def test_from_country_code(self):
        assert _get_dc_country({"country_code": "IE"}) == "IE"

    def test_from_nation(self):
        assert _get_dc_country({"nation": "DE"}) == "DE"

    def test_returns_empty(self):
        assert _get_dc_country({}) == ""


class TestGetDcCity:
    def test_from_city(self):
        assert _get_dc_city({"city": "Dublin"}) == "Dublin"

    def test_from_location(self):
        assert _get_dc_city({"location": "London"}) == "London"

    def test_from_metro(self):
        assert _get_dc_city({"metro": "Ashburn"}) == "Ashburn"

    def test_returns_empty(self):
        assert _get_dc_city({}) == ""


class TestField:
    def test_picks_first_match(self):
        assert _field({"lon": "-77.5", "lng": "-75.0"}, "lon", "lng") == "-77.5"

    def test_returns_empty_when_not_found(self):
        assert _field({"a": "1"}, "x", "y") == ""

    def test_skips_empty_values(self):
        assert _field({"lon": "", "lng": "-75.0"}, "lon", "lng") == "-75.0"


class TestParseMw:
    def test_from_capacity_mw(self):
        assert _parse_mw({"capacity_mw": 500}) == 500.0

    def test_from_current_power_mw(self):
        assert _parse_mw({"current_power_mw": "100"}) == 100.0

    def test_from_mw(self):
        assert _parse_mw({"mw": 250}) == 250.0

    def test_returns_none_when_missing(self):
        assert _parse_mw({}) is None

    def test_returns_none_on_invalid(self):
        assert _parse_mw({"mw": "nope"}) is None

    def test_rounds_to_one_decimal(self):
        assert _parse_mw({"mw": 123.456}) == 123.5


class TestLoadDatacentersFromGeojson:
    def test_loads_valid_dcs(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path)
        assert len(dcs) == 4

    def test_dc_fields(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path)
        alpha = next(d for d in dcs if d["n"] == "DC Alpha")
        assert alpha["op"] == "OpCorp"
        assert alpha["c"] == "US"
        assert alpha["city"] == "Ashburn"
        assert alpha["lat"] == 39.0
        assert alpha["lon"] == -77.5
        assert alpha["mw"] == 500.0
        assert alpha["mapped_status"] == "mapped"

    def test_deduplicates_by_name(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path)
        alpha_count = sum(1 for d in dcs if d["n"] == "DC Alpha")
        assert alpha_count == 1

    def test_skips_empty_name(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path)
        names = [d["n"] for d in dcs]
        assert "" not in names

    def test_skips_bad_coords(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path)
        names = [d["n"] for d in dcs]
        assert "Bad Coord DC" not in names

    def test_custom_precision(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path, coordinate_precision="city_level")
        assert dcs[0]["coordinate_precision"] == "city_level"

    def test_precision_from_props_takes_priority(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path, coordinate_precision="metro_level")
        with_precision = next(d for d in dcs if d["n"] == "DC With Precision")
        assert with_precision["coordinate_precision"] == "exact_address"
        without_precision = next(d for d in dcs if d["n"] == "DC Alpha")
        assert without_precision["coordinate_precision"] == "metro_level"

    def test_override_source_name(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path, source_name="custom_source")
        assert dcs[0]["coordinate_source"] == "custom_source"

    def test_override_confidence(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path, confidence=0.7)
        assert dcs[0]["confidence"] == 0.7

    def test_returns_empty_on_missing_file(self, tmp_path):
        dcs = load_datacenters_from_geojson(tmp_path / "nonexistent.geojson")
        assert dcs == []

    def test_uses_props_for_operator_and_country_fallback(self):
        path = FIXTURES / "sample_data_centers.geojson"
        dcs = load_datacenters_from_geojson(path)
        beta = next(d for d in dcs if d["n"] == "DC Beta")
        assert beta["op"] == "DataCo"
        assert beta["c"] == "IE"
        assert beta["city"] == "Dublin"


class TestLoadDatacentersFromCsv:
    def test_loads_valid_dcs(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path)
        assert len(dcs) == 2

    def test_dc_fields(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path)
        gamma = next(d for d in dcs if d["n"] == "CSV DC Gamma")
        assert gamma["op"] == "CloudInc"
        assert gamma["c"] == "US"
        assert gamma["city"] == "Boardman"
        assert gamma["lat"] == 45.84
        assert gamma["lon"] == -119.68
        assert gamma["mw"] == 250.0
        assert gamma["mapped_status"] == "mapped"

    def test_skips_missing_coords(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path)
        names = [d["n"] for d in dcs]
        assert "CSV DC No Coords" not in names

    def test_skips_bad_coords(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path)
        names = [d["n"] for d in dcs]
        assert "CSV DC Bad Lon" not in names

    def test_coordinate_precision_from_csv(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path)
        gamma = next(d for d in dcs if d["n"] == "CSV DC Gamma")
        assert gamma["coordinate_precision"] == "metro_level"

    def test_deduplicates_by_name(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path)
        gamma_count = sum(1 for d in dcs if d["n"] == "CSV DC Gamma")
        assert gamma_count == 1

    def test_override_source_name(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path, source_name="custom_source")
        assert dcs[0]["coordinate_source"] == "custom_source"

    def test_override_confidence(self):
        path = FIXTURES / "sample_data_centers.csv"
        dcs = load_datacenters_from_csv(path, confidence=0.6)
        assert dcs[0]["confidence"] == 0.6

    def test_returns_empty_on_missing_file(self, tmp_path):
        dcs = load_datacenters_from_csv(tmp_path / "nonexistent.csv")
        assert dcs == []
