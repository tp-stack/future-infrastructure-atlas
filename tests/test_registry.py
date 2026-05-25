from atlas.registry import (
    load_datasets,
    load_layers,
    load_sources,
    validate_all_registries,
    validate_commercial_api_policy,
    validate_layers,
    validate_sources,
)


def test_validate_all_registries_returns_ok():
    result = validate_all_registries()

    assert result.ok, result.errors


def test_sources_have_required_fields():
    required_fields = {
        "source_id",
        "source_key",
        "source_name",
        "category",
        "source_type",
        "reliability_class",
        "license",
        "url",
        "update_frequency",
        "allowed_usage",
        "access_method",
        "requires_license_review",
        "expected_formats",
        "geographic_scope",
        "notes",
    }

    for source in load_sources():
        assert required_fields <= set(source)


def test_datasets_have_required_fields():
    required_fields = {
        "dataset_key",
        "display_name",
        "source_key",
        "category",
        "target_layer",
        "expected_geometry_type",
        "expected_format",
        "update_frequency",
        "license",
        "sensitivity_level",
        "allowed_precision",
        "ingestion_status",
        "raw_storage_policy",
        "processed_storage_policy",
        "checksum_required",
        "validation_required",
        "notes",
    }

    for dataset in load_datasets():
        assert required_fields <= set(dataset)


def test_layers_have_required_fields():
    required_fields = {
        "layer_id",
        "display_name",
        "category",
        "geometry_type",
        "min_zoom",
        "max_zoom",
        "sensitivity_level",
        "allowed_precision",
        "required_fields",
        "optional_fields",
        "source_dataset_keys",
        "confidence_policy",
        "public_visibility",
        "enterprise_visibility",
    }

    for layer in load_layers():
        assert required_fields <= set(layer)


def test_every_dataset_source_key_exists():
    source_keys = {source["source_key"] for source in load_sources()}

    assert all(dataset["source_key"] in source_keys for dataset in load_datasets())


def test_every_dataset_target_layer_exists():
    layer_ids = {layer["layer_id"] for layer in load_layers()}

    assert all(dataset["target_layer"] in layer_ids for dataset in load_datasets())


def test_every_layer_source_dataset_key_exists():
    dataset_keys = {dataset["dataset_key"] for dataset in load_datasets()}

    for layer in load_layers():
        assert set(layer["source_dataset_keys"]) <= dataset_keys


def test_public_high_sensitivity_exact_precision_rule_is_enforced():
    bad_layer = {
        "layer_id": "unsafe_public_layer",
        "display_name": "Unsafe Public Layer",
        "category": "test",
        "geometry_type": "Point",
        "min_zoom": 1,
        "max_zoom": 10,
        "sensitivity_level": "high",
        "allowed_precision": "exact_public",
        "required_fields": ["asset_id"],
        "optional_fields": [],
        "source_dataset_keys": ["wri_global_power_plants"],
        "confidence_policy": "test_policy",
        "public_visibility": True,
        "enterprise_visibility": True,
    }

    result = validate_layers([bad_layer])

    assert not result.ok
    assert any("cannot be public with exact precision" in error for error in result.errors)


def test_duplicate_source_keys_are_detected():
    source = load_sources()[0].copy()
    duplicate = source.copy()

    result = validate_sources([source, duplicate])

    assert not result.ok
    assert any("Duplicate source key" in error for error in result.errors)


def test_commercial_api_policy_is_valid():
    result = validate_commercial_api_policy()

    assert result.ok, result.errors


def test_commercial_api_policy_detects_overlapping_allowed_and_blocked_usage():
    result = validate_commercial_api_policy(
        {
            "required_rights_fields": [
                "commercial_api_allowed",
                "redistribution_allowed",
                "attribution_required",
                "share_alike_risk",
                "license_review_status",
                "rights_evidence_path",
            ],
            "safe_allowed_usage": ["owned"],
            "blocked_allowed_usage": ["owned"],
            "blocked_license_values": ["to_verify"],
            "approved_license_review_statuses": ["approved"],
        }
    )

    assert not result.ok
    assert any("overlap" in error for error in result.errors)
