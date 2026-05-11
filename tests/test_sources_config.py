from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_config_files_are_valid_yaml():
    for config_path in (PROJECT_ROOT / "config").glob("*.yaml"):
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        assert isinstance(data, dict), config_path


def test_sources_have_reliability_class_and_license():
    with (PROJECT_ROOT / "config" / "sources.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    sources = data["sources"]
    assert sources
    for source in sources:
        assert source.get("source_id")
        assert source.get("reliability_class") in {"A", "B", "C", "D", "P"}
        assert source.get("license")
