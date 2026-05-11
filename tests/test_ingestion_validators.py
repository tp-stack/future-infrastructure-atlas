from __future__ import annotations

import pytest

from atlas.ingestion.validators import (
    validate_latitude,
    validate_longitude,
    validate_records,
    validate_required_fields,
)


class TestValidateRequiredFields:
    def test_all_fields_present(self):
        record = {"name": "A", "country": "B", "fuel_type": "C"}
        missing = validate_required_fields(record, ["name", "country", "fuel_type"])
        assert missing == []

    def test_missing_field(self):
        record = {"name": "A"}
        missing = validate_required_fields(record, ["name", "country"])
        assert missing == ["country"]

    def test_empty_field_is_missing(self):
        record = {"name": "A", "country": ""}
        missing = validate_required_fields(record, ["name", "country"])
        assert missing == ["country"]

    def test_none_field_is_missing(self):
        record = {"name": "A", "country": None}
        missing = validate_required_fields(record, ["name", "country"])
        assert missing == ["country"]

    def test_blank_field_is_missing(self):
        record = {"name": "A", "country": "   "}
        missing = validate_required_fields(record, ["name", "country"])
        assert missing == ["country"]


class TestValidateLatitude:
    def test_valid_latitude(self):
        assert validate_latitude("41.8902") == 41.8902
        assert validate_latitude(0) == 0
        assert validate_latitude(-90) == -90
        assert validate_latitude(90) == 90

    def test_invalid_latitude_too_high(self):
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            validate_latitude(91)

    def test_invalid_latitude_too_low(self):
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            validate_latitude(-91)

    def test_non_numeric_latitude(self):
        with pytest.raises(ValueError):
            validate_latitude("abc")


class TestValidateLongitude:
    def test_valid_longitude(self):
        assert validate_longitude("12.4924") == 12.4924
        assert validate_longitude(0) == 0
        assert validate_longitude(-180) == -180
        assert validate_longitude(180) == 180

    def test_invalid_longitude_too_high(self):
        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            validate_longitude(181)

    def test_invalid_longitude_too_low(self):
        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            validate_longitude(-181)

    def test_non_numeric_longitude(self):
        with pytest.raises(ValueError):
            validate_longitude("xyz")


class TestValidateRecords:
    def test_valid_records_pass(self):
        records = [
            {"name": "A", "country": "B", "fuel_type": "C", "latitude": "0", "longitude": "0"}
        ]
        valid, rejected = validate_records(records, ["name", "country"])
        assert len(valid) == 1
        assert rejected == []

    def test_record_with_missing_field_is_rejected(self):
        records = [
            {"name": "A"}
        ]
        valid, rejected = validate_records(records, ["name", "country"])
        assert valid == []
        assert len(rejected) == 1
        assert any("missing required field: country" in err for err in rejected[0]["errors"])

    def test_record_with_invalid_lat_is_rejected(self):
        records = [
            {"name": "A", "country": "B", "fuel_type": "C", "latitude": "999", "longitude": "0"}
        ]
        valid, rejected = validate_records(records, ["name", "country", "fuel_type"])
        assert valid == []
        assert len(rejected) == 1

    def test_mixed_valid_and_invalid(self):
        records = [
            {"name": "Good", "country": "IT", "fuel_type": "solar", "latitude": "41.89", "longitude": "12.49"},
            {"name": "Bad", "country": "", "fuel_type": "wind", "latitude": "0", "longitude": "0"},
            {},
        ]
        valid, rejected = validate_records(records, ["name", "country", "fuel_type"])
        assert len(valid) == 1
        assert len(rejected) == 2

    def test_empty_records_list(self):
        valid, rejected = validate_records([], ["name"])
        assert valid == []
        assert rejected == []
