from pathlib import Path

import yaml

from atlas.storage import validate_repo_file_safety


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_repository_has_no_unsafe_files():
    assert validate_repo_file_safety(PROJECT_ROOT) == []


def test_layers_have_sensitivity_level_and_required_fields():
    with (PROJECT_ROOT / "config" / "layers.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    layers = data["layers"]
    assert layers
    for layer in layers:
        assert layer.get("layer_id")
        assert layer.get("sensitivity_level") in {"low", "medium", "high"}
        assert isinstance(layer.get("required_fields"), list)
        assert layer["required_fields"]
