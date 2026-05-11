"""Small validation helpers for Atlas configuration files."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def missing_keys(item: Mapping[str, object], required_keys: Iterable[str]) -> list[str]:
    """Return required keys missing from a mapping."""

    return [key for key in required_keys if key not in item]


def require_keys(item: Mapping[str, object], required_keys: Iterable[str], item_name: str) -> None:
    """Raise a ValueError if a mapping is missing required keys."""

    missing = missing_keys(item, required_keys)
    if missing:
        raise ValueError(f"{item_name} missing required keys: {', '.join(missing)}")
