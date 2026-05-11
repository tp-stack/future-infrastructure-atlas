"""Configuration loading for FUTURE Infrastructure Atlas."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

database_host = os.environ.get("DATABASE_HOST", "localhost")
database_port = int(os.environ.get("DATABASE_PORT", "5432"))
database_name = os.environ.get("DATABASE_NAME", "future_atlas")
database_user = os.environ.get("DATABASE_USER", "future_atlas")
database_password = os.environ.get("DATABASE_PASSWORD", "future_atlas_dev_password")
database_url = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{database_user}:{database_password}@{database_host}:{database_port}/{database_name}",
)


def load_yaml_config(config_name: str, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Load a YAML config file from the repository config directory."""

    root = Path(repo_root).resolve() if repo_root is not None else PROJECT_ROOT
    config_path = root / "config" / config_name
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {config_path}")
    return data


@lru_cache(maxsize=1)
def get_storage_config() -> dict[str, Any]:
    """Return the repository storage configuration."""

    return load_yaml_config("storage.yaml")


def get_database_settings() -> dict[str, str | int]:
    """Return database settings from environment variables with local defaults."""

    return {
        "database_host": database_host,
        "database_port": database_port,
        "database_name": database_name,
        "database_user": database_user,
        "database_password": database_password,
        "database_url": database_url,
    }
