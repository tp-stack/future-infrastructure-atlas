"""Registry loading and validation for sources, datasets, and layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


@dataclass
class ValidationResult:
    """Structured validation result used by registry checks."""

    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.ok = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def extend(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.ok = self.ok and other.ok


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file as a mapping."""

    yaml_path = Path(path)
    if not yaml_path.is_absolute():
        candidate = PROJECT_ROOT / yaml_path
        yaml_path = candidate if candidate.exists() else CONFIG_DIR / yaml_path
    with yaml_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {yaml_path}")
    return data


def _policy() -> dict[str, Any]:
    return load_yaml("provenance_policy.yaml")


def load_sources() -> list[dict[str, Any]]:
    return list(load_yaml("sources.yaml").get("sources", []))


def load_datasets() -> list[dict[str, Any]]:
    return list(load_yaml("datasets.yaml").get("datasets", []))


def load_layers() -> list[dict[str, Any]]:
    return list(load_yaml("layers.yaml").get("layers", []))


def load_commercial_api_policy() -> dict[str, Any]:
    return dict(load_yaml("commercial_api.yaml").get("commercial_api", {}))


def get_source_by_key(source_key: str) -> dict[str, Any] | None:
    return next((source for source in load_sources() if source.get("source_key") == source_key), None)


def get_dataset_by_key(dataset_key: str) -> dict[str, Any] | None:
    return next((dataset for dataset in load_datasets() if dataset.get("dataset_key") == dataset_key), None)


def get_layer_by_id(layer_id: str) -> dict[str, Any] | None:
    return next((layer for layer in load_layers() if layer.get("layer_id") == layer_id), None)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _validate_required(
    result: ValidationResult,
    item: dict[str, Any],
    required_fields: list[str],
    item_label: str,
) -> None:
    for field_name in required_fields:
        if field_name not in item or _is_empty(item[field_name]):
            result.add_error(f"{item_label} missing required field: {field_name}")


def _validate_duplicates(
    result: ValidationResult,
    items: list[dict[str, Any]],
    key_name: str,
    label: str,
) -> None:
    seen: set[str] = set()
    for item in items:
        key = item.get(key_name)
        if not key:
            continue
        if key in seen:
            result.add_error(f"Duplicate {label} key: {key}")
        seen.add(key)


def validate_sources(sources: list[dict[str, Any]] | None = None) -> ValidationResult:
    """Validate source registry records."""

    result = ValidationResult()
    policy = _policy()
    source_rows = load_sources() if sources is None else sources
    required_fields = policy["required_source_fields"]
    allowed_source_types = set(policy["allowed_source_types"])
    allowed_reliability_classes = set(policy["allowed_reliability_classes"])
    allowed_access_methods = set(policy.get("allowed_access_methods", []))

    _validate_duplicates(result, source_rows, "source_key", "source")

    for source in source_rows:
        label = f"source {source.get('source_key', '<missing>')}"
        _validate_required(result, source, required_fields, label)

        if source.get("source_type") not in allowed_source_types:
            result.add_error(f"{label} has invalid source_type: {source.get('source_type')}")
        if source.get("reliability_class") not in allowed_reliability_classes:
            result.add_error(f"{label} has invalid reliability_class: {source.get('reliability_class')}")
        if source.get("access_method") not in allowed_access_methods:
            result.add_error(f"{label} has invalid access_method: {source.get('access_method')}")
        if _is_empty(source.get("license")):
            result.add_error(f"{label} has empty license")
        if _is_empty(source.get("allowed_usage")):
            result.add_error(f"{label} has empty allowed_usage")
        if source.get("to_verify") is True:
            result.add_warning(f"{label} contains unverified source metadata")

    return result


def validate_datasets(datasets: list[dict[str, Any]] | None = None) -> ValidationResult:
    """Validate dataset registry records."""

    result = ValidationResult()
    policy = _policy()
    dataset_rows = load_datasets() if datasets is None else datasets
    required_fields = policy["required_dataset_fields"]
    allowed_sensitivity_levels = set(policy["allowed_sensitivity_levels"])
    allowed_precision_values = set(policy["allowed_precision_values"])
    allowed_ingestion_statuses = set(policy.get("allowed_ingestion_statuses", []))

    _validate_duplicates(result, dataset_rows, "dataset_key", "dataset")

    for dataset in dataset_rows:
        label = f"dataset {dataset.get('dataset_key', '<missing>')}"
        _validate_required(result, dataset, required_fields, label)

        if dataset.get("sensitivity_level") not in allowed_sensitivity_levels:
            result.add_error(f"{label} has invalid sensitivity_level: {dataset.get('sensitivity_level')}")
        if dataset.get("allowed_precision") not in allowed_precision_values:
            result.add_error(f"{label} has invalid allowed_precision: {dataset.get('allowed_precision')}")
        if dataset.get("ingestion_status") not in allowed_ingestion_statuses:
            result.add_error(f"{label} has invalid ingestion_status: {dataset.get('ingestion_status')}")
        if _is_empty(dataset.get("license")):
            result.add_error(f"{label} has empty license")

    return result


def validate_layers(layers: list[dict[str, Any]] | None = None) -> ValidationResult:
    """Validate layer registry records."""

    result = ValidationResult()
    policy = _policy()
    layer_rows = load_layers() if layers is None else layers
    required_fields = policy["required_layer_fields"]
    allowed_sensitivity_levels = set(policy["allowed_sensitivity_levels"])
    allowed_precision_values = set(policy["allowed_precision_values"])

    _validate_duplicates(result, layer_rows, "layer_id", "layer")

    for layer in layer_rows:
        label = f"layer {layer.get('layer_id', '<missing>')}"
        _validate_required(result, layer, required_fields, label)

        if layer.get("sensitivity_level") not in allowed_sensitivity_levels:
            result.add_error(f"{label} has invalid sensitivity_level: {layer.get('sensitivity_level')}")
        if layer.get("allowed_precision") not in allowed_precision_values:
            result.add_error(f"{label} has invalid allowed_precision: {layer.get('allowed_precision')}")
        if not isinstance(layer.get("required_fields"), list) or not layer.get("required_fields"):
            result.add_error(f"{label} required_fields must be a non-empty list")
        if not isinstance(layer.get("source_dataset_keys"), list) or not layer.get("source_dataset_keys"):
            result.add_error(f"{label} source_dataset_keys must be a non-empty list")
        if _is_empty(layer.get("confidence_policy")):
            result.add_error(f"{label} has empty confidence_policy")
        if (
            layer.get("public_visibility") is True
            and layer.get("sensitivity_level") in {"high", "restricted"}
            and layer.get("allowed_precision") == "exact_public"
        ):
            result.add_error(f"{label} cannot be public with exact precision and high/restricted sensitivity")

    return result


def validate_registry_links() -> ValidationResult:
    """Validate source -> dataset -> layer cross references."""

    result = ValidationResult()
    sources = load_sources()
    datasets = load_datasets()
    layers = load_layers()

    source_keys = {source["source_key"] for source in sources if source.get("source_key")}
    dataset_keys = {dataset["dataset_key"] for dataset in datasets if dataset.get("dataset_key")}
    layer_ids = {layer["layer_id"] for layer in layers if layer.get("layer_id")}

    for dataset in datasets:
        dataset_key = dataset.get("dataset_key", "<missing>")
        source_key = dataset.get("source_key")
        target_layer = dataset.get("target_layer")
        if source_key not in source_keys:
            result.add_error(f"dataset {dataset_key} references unknown source_key: {source_key}")
        if target_layer not in layer_ids:
            result.add_error(f"dataset {dataset_key} references unknown target_layer: {target_layer}")

    for layer in layers:
        layer_id = layer.get("layer_id", "<missing>")
        for dataset_key in layer.get("source_dataset_keys", []) or []:
            if dataset_key not in dataset_keys:
                result.add_error(f"layer {layer_id} references unknown dataset_key: {dataset_key}")

    return result


def validate_all_registries() -> ValidationResult:
    """Validate sources, datasets, layers, and all registry links."""

    result = ValidationResult()
    result.extend(validate_sources())
    result.extend(validate_datasets())
    result.extend(validate_layers())
    result.extend(validate_registry_links())
    result.extend(validate_commercial_api_policy())
    return result


def validate_commercial_api_policy(policy: dict[str, Any] | None = None) -> ValidationResult:
    """Validate the commercial API rights policy overlay."""

    result = ValidationResult()
    policy_data = load_commercial_api_policy() if policy is None else policy
    required_lists = [
        "required_rights_fields",
        "safe_allowed_usage",
        "blocked_allowed_usage",
        "blocked_license_values",
        "approved_license_review_statuses",
    ]
    for key in required_lists:
        if not isinstance(policy_data.get(key), list) or not policy_data.get(key):
            result.add_error(f"commercial_api policy missing non-empty list: {key}")

    required_rights_fields = set(policy_data.get("required_rights_fields", []))
    expected_rights_fields = {
        "commercial_api_allowed",
        "redistribution_allowed",
        "attribution_required",
        "share_alike_risk",
        "license_review_status",
        "rights_evidence_path",
    }
    missing = expected_rights_fields - required_rights_fields
    if missing:
        result.add_error(f"commercial_api policy missing required rights fields: {sorted(missing)}")

    if set(policy_data.get("safe_allowed_usage", [])) & set(policy_data.get("blocked_allowed_usage", [])):
        result.add_error("commercial_api policy safe_allowed_usage and blocked_allowed_usage overlap")

    return result
