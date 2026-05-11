from __future__ import annotations

from typing import Any


def validate_required_fields(record: dict[str, Any], required_fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        val = record.get(field)
        if val is None or str(val).strip() == "":
            missing.append(field)
    return missing


def validate_latitude(value: Any) -> float:
    lat = float(value)
    if lat < -90 or lat > 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    return lat


def validate_longitude(value: Any) -> float:
    lng = float(value)
    if lng < -180 or lng > 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lng}")
    return lng


def validate_records(
    records: list[dict[str, Any]],
    required_fields: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for i, record in enumerate(records):
        errors: list[str] = []

        missing = validate_required_fields(record, required_fields)
        for field in missing:
            errors.append(f"record[{i}] missing required field: {field}")

        lat_val = record.get("latitude")
        lng_val = record.get("longitude")
        if lat_val is not None and str(lat_val).strip():
            try:
                validate_latitude(lat_val)
            except (ValueError, TypeError) as exc:
                errors.append(f"record[{i}] invalid latitude: {exc}")
        if lng_val is not None and str(lng_val).strip():
            try:
                validate_longitude(lng_val)
            except (ValueError, TypeError) as exc:
                errors.append(f"record[{i}] invalid longitude: {exc}")

        if errors:
            rejected.append({"index": i, "record": record, "errors": errors})
        else:
            valid.append(record)

    return valid, rejected
