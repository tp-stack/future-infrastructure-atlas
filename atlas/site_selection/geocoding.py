"""Reverse geocoding enrichment interface for site selection candidates.

This module provides a clean interface for reverse geocoding (country, region, municipality)
lookups. The MVP uses a lookup table derived from the existing atlas_web_data.json
(power plants and data centers) to provide real administrative data where possible.
Implementers can replace the implementation with a proper geocoding service (e.g.,
Nominatim, GeoNames, PostGIS reverse geocoding) without changing the candidate generator.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Protocol, Tuple

# Default geocoder that returns Unknown for all fields.
class DefaultReverseGeocoder:
    def reverse_geocode(self, lat: float, lon: float) -> dict[str, str]:
        return {
            "country": "Unknown",
            "region": "Unknown",
            "municipality": "Unknown",
        }

# Interface for geocoders.
class ReverseGeocoder(Protocol):
    def reverse_geocode(self, lat: float, lon: float) -> dict[str, str]:
        ...

# Global geocoder instance.
_current_geocoder: ReverseGeocoder = DefaultReverseGeocoder()

# Lookup table for administrative data: key = (lat_rounded, lon_rounded), value = dict with keys.
_admin_lookup: Dict[Tuple[float, float], dict[str, str]] = {}


def _build_admin_lookup() -> None:
    """Build a lookup table for administrative data from atlas_web_data.json."""
    global _admin_lookup
    # Try to locate the atlas_web_data.json file.
    possible_paths = [
        # Relative to this file.
        os.path.join(os.path.dirname(__file__), "../../../../data/processed/web/atlas_web_data.json"),
        # Alternative relative path.
        os.path.join(os.path.dirname(__file__), "../../../data/processed/web/atlas_web_data.json"),
        # Absolute path in container.
        "/data/processed/web/atlas_web_data.json",
    ]
    data_path = None
    for path in possible_paths:
        if os.path.exists(path):
            data_path = path
            break
    if data_path is None:
        # If we can't find the file, keep the lookup empty.
        return
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Extract power plants and data centers.
        features = []
        if "power_plants" in data:
            features.extend(data["power_plants"])
        if "data_centers" in data:
            features.extend(data["data_centers"])
        # Build lookup table: round coordinates to 1 decimal place (about 11km).
        for f in features:
            lat = f.get("lat")
            lon = f.get("lon")
            country = f.get("c")  # In atlas_web_data.json, country is stored as 'c'.
            region = f.get("r")   # Region is stored as 'r'.
            municipality = f.get("m")  # Municipality is stored as 'm'.
            if lat is not None and lon is not None:
                key = (round(lat, 1), round(lon, 1))
                # Only store if we have at least country known.
                if country is not None and country != "":
                    # If multiple points map to the same key, keep the first one.
                    if key not in _admin_lookup:
                        _admin_lookup[key] = {
                            "country": country if country != "" else "Unknown",
                            "region": region if region != "" else "Unknown",
                            "municipality": municipality if municipality != "" else "Unknown",
                        }
    except Exception:
        # If anything goes wrong, keep the lookup empty.
        pass


# Build the lookup table on module import.
_build_admin_lookup()


class AdminLookupGeocoder:
    """Geocoder that uses the precomputed lookup table for administrative data."""

    def reverse_geocode(self, lat: float, lon: float) -> dict[str, str]:
        key = (round(lat, 1), round(lon, 1))
        if key in _admin_lookup:
            return _admin_lookup[key]
        # Fallback to default.
        return DefaultReverseGeocoder().reverse_geocode(lat, lon)


def set_geocoder(geocoder: ReverseGeocoder) -> None:
    global _current_geocoder
    _current_geocoder = geocoder


def get_geocoder() -> ReverseGeocoder:
    return _current_geocoder


def reverse_geocode(lat: float, lon: float) -> dict[str, str]:
    return _current_geocoder.reverse_geocode(lat, lon)