"""Candidate location generator from bbox or polygon input."""

from __future__ import annotations

import math
import uuid
from typing import Any

from atlas.site_selection.confidence import compute_confidence_score, is_human_review_required
from atlas.site_selection.evidence import generate_evidence_summary
from atlas.site_selection.exclusions import check_exclusions
from atlas.site_selection.geocoding import reverse_geocode
from atlas.site_selection.infrastructure_index import (
    get_substation_points,
    get_high_voltage_points,
    get_power_plant_points,
    get_ixp_proxy_points,
    get_facility_points,
    get_data_center_points,
    get_cable_landing_points,
    load_infrastructure_index,
    load_telecom_index,
)
from atlas.site_selection.models import CandidateSite, MissingDataFlag
from atlas.site_selection.persistence import store_query_batch
from atlas.site_selection.profiles import COMPUTE_PROFILES
from atlas.site_selection.scoring import score_candidate


def _generate_grid_cells(bbox: tuple[float, float, float, float], cell_size_deg: float) -> list[tuple[float, float]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    cells: list[tuple[float, float]] = []
    lon = min_lon
    while lon < max_lon:
        lat = min_lat
        while lat < max_lat:
            centroid_lon = lon + cell_size_deg / 2
            centroid_lat = lat + cell_size_deg / 2
            if centroid_lon <= max_lon and centroid_lat <= max_lat:
                cells.append((centroid_lon, centroid_lat))
            lat += cell_size_deg
        lon += cell_size_deg
    return cells


def _area_ha_from_bbox(bbox: tuple[float, float, float, float], lat: float) -> float:
    min_lon, min_lat, max_lon, max_lat = bbox
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    lat_rad = math.radians(lat)
    km_per_deg_lon = 111.32 * math.cos(lat_rad)
    km_per_deg_lat = 111.32
    width_km = lon_span * km_per_deg_lon
    height_km = lat_span * km_per_deg_lat
    area_sq_km = width_km * height_km
    return area_sq_km * 100.0


def geometry_from_bbox(bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


class _ProxyDistance:
    """Returned by proxy distance functions to indicate source type and level.

    proxy_level:
      None   — no data available
      'substation'    — real OSM substation point (best)
      'high_voltage'  — OSM power line proxy (medium)
      'power_plant'   — WRI power plant proxy (weakest)
      'data_center'   — PeeringDB data center proxy for fiber
    """

    def __init__(self, distance_km: float | None, proxy_level: str | None):
        self.distance_km = distance_km
        self.proxy_level = proxy_level

    @property
    def is_proxy(self) -> bool:
        return self.proxy_level is not None


def _nearest_distance(lat: float, lon: float, points: list[dict]) -> tuple[float | None, float | None]:
    """Compute nearest Euclidean distance (km) and return (distance, voltage_kv)."""
    if not points:
        return None, None
    best_dist: float | None = None
    best_voltage: float | None = None
    for pt in points:
        pt_lat = pt.get("lat")
        pt_lon = pt.get("lon")
        if pt_lat is None or pt_lon is None:
            continue
        d = math.sqrt((lat - pt_lat) ** 2 + (lon - pt_lon) ** 2) * 111.32
        if best_dist is None or d < best_dist:
            best_dist = d
            best_voltage = pt.get("v")
    return best_dist, best_voltage


def _get_grid_distance(
    lat: float, lon: float,
    substations: list[dict],
    hv_points: list[dict],
    power_plants: list[dict],
) -> _ProxyDistance:
    """Compute nearest grid distance using priority: substations > HV > power_plants.

    Returns the closest distance and the proxy level of the source used.
    """
    dist, voltage = _nearest_distance(lat, lon, substations)
    if dist is not None:
        return _ProxyDistance(dist, "substation")
    dist, _ = _nearest_distance(lat, lon, hv_points)
    if dist is not None:
        return _ProxyDistance(dist, "high_voltage")
    dist, _ = _nearest_distance(lat, lon, power_plants)
    if dist is not None:
        return _ProxyDistance(dist, "power_plant")
    return _ProxyDistance(None, None)


def _get_telecom_fiber_distance(
    lat: float, lon: float,
    ixp_proxy: list[dict],
    facility_points: list[dict],
    data_center_points: list[dict],
    cable_landing_points: list[dict],
) -> _ProxyDistance:
    """Compute nearest fiber/telecom distance using priority: IXP > facility > DC > cable.

    Returns the closest distance and the proxy level of the source used.
    """
    dist, _ = _nearest_distance(lat, lon, ixp_proxy)
    if dist is not None:
        return _ProxyDistance(dist, "ixp_proxy")
    dist, _ = _nearest_distance(lat, lon, facility_points)
    if dist is not None:
        return _ProxyDistance(dist, "facility")
    dist, _ = _nearest_distance(lat, lon, data_center_points)
    if dist is not None:
        return _ProxyDistance(dist, "data_center")
    dist, _ = _nearest_distance(lat, lon, cable_landing_points)
    if dist is not None:
        return _ProxyDistance(dist, "cable_landing")
    return _ProxyDistance(None, None)


def generate_candidates_from_bbox(
    bbox: tuple[float, float, float, float],
    profile_key: str = "regional_compute_5mw",
    scoring_profile_key: str = "default",
    limit: int = 25,
    include_excluded: bool = False,
    existing_infrastructure: dict[str, Any] | None = None,
) -> tuple[list[CandidateSite], str]:
    profile = COMPUTE_PROFILES.get(profile_key)
    if profile is None:
        raise ValueError(f"Unknown compute profile: {profile_key}")

    min_lon, min_lat, max_lon, max_lat = bbox
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat

    num_cells = max(1, min(50, int(math.sqrt(limit * 2))))
    cell_size_lon = lon_span / num_cells if lon_span > 0 else 0.1
    cell_size_lat = lat_span / num_cells if lat_span > 0 else 0.1

    cells = _generate_grid_cells(bbox, min(cell_size_lon, cell_size_lat))

    # Load infrastructure index with tiered grid sources
    # and telecom index for fiber/interconnection proximity
    if existing_infrastructure is not None:
        infra = existing_infrastructure
        using_proxy_sources = True
        substations = infra.get("substations", [])
        hv_points = infra.get("high_voltage_points", [])
        power_plants_for_grid = infra.get("power_plants", [])
    else:
        infra = load_infrastructure_index()
        using_proxy_sources = True
        substations = infra.get("features", {}).get("substation_points", [])
        hv_points = infra.get("features", {}).get("high_voltage_points", [])
        power_plants_for_grid = infra.get("features", {}).get("power_plant_points", [])

    # Load telecom index for fiber/interconnection hierarchy
    telecom = load_telecom_index()
    ixp_proxy = telecom.get("features", {}).get("ixp_proxy_points", [])
    facility_points = telecom.get("features", {}).get("facility_points", [])
    data_center_points = infra.get("features", {}).get("data_center_points", [])
    cable_landing_points = infra.get("features", {}).get("cable_landing_points", [])

    area = {"type": "bbox", "coordinates": list(bbox)}

    candidates: list[CandidateSite] = []
    for lon, lat in cells:
        if len(candidates) >= limit * 3:
            break

        area_ha = _area_ha_from_bbox(bbox, lat)
        grid_proxy = _get_grid_distance(lat, lon, substations, hv_points, power_plants_for_grid)
        fiber_proxy = _get_telecom_fiber_distance(lat, lon, ixp_proxy, facility_points, data_center_points, cable_landing_points)
        ixp_dist, _ = _nearest_distance(lat, lon, ixp_proxy)

        geo = reverse_geocode(lat, lon)

        # Extract voltage from the closest grid point if available
        sub_voltage = None
        hv_line_kv = None
        if grid_proxy.proxy_level == "substation":
            dist_sub, sub_voltage = _nearest_distance(lat, lon, substations)
        elif grid_proxy.proxy_level == "high_voltage":
            _, hv_line_kv = _nearest_distance(lat, lon, hv_points)

        candidate = CandidateSite(
            candidate_site_id=f"cs-{uuid.uuid4().hex[:12]}",
            country=geo["country"],
            region=geo["region"],
            municipality=geo["municipality"],
            lat=lat,
            lon=lon,
            geometry=geometry_from_bbox(bbox),
            area_ha=area_ha,
            compute_profile=profile_key,
            nearest_substation_km=grid_proxy.distance_km,
            nearest_power_line_km=grid_proxy.distance_km,
            substation_voltage_kv=sub_voltage,
            nearest_high_voltage_line_kv=hv_line_kv,
            nearest_fiber_km=fiber_proxy.distance_km,
            fiber_proxy_level=fiber_proxy.proxy_level,
            nearest_ixp_km=ixp_dist,
            estimated_grid_capacity_mw=None,
            flood_risk_score=None,
            water_stress_score=None,
            regulatory_stability_score=None,
            market_demand_score=None,
            zoning_compatibility_score=None,
            incentive_score=30.0,
        )

        if geo["country"] == "Unknown":
            candidate.missing_data_flags.append(MissingDataFlag.ADMIN_GEOCODING_NOT_AVAILABLE.value)

        score_candidate(candidate, profile, scoring_profile_key)

        # Always set GRID_CAPACITY_UNKNOWN since we never have real utility capacity
        if using_proxy_sources and grid_proxy.distance_km is not None:
            if MissingDataFlag.GRID_CAPACITY_UNKNOWN.value not in candidate.missing_data_flags:
                candidate.missing_data_flags.append(MissingDataFlag.GRID_CAPACITY_UNKNOWN.value)

        if fiber_proxy.is_proxy and fiber_proxy.distance_km is not None:
            if MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value not in candidate.missing_data_flags:
                candidate.missing_data_flags.append(MissingDataFlag.FIBER_AVAILABILITY_UNKNOWN.value)

        compute_confidence_score(candidate, scoring_profile_key)
        check_exclusions(candidate, profile)
        candidate.human_review_required = is_human_review_required(candidate, profile)
        candidate.evidence_summary = generate_evidence_summary(candidate)

        if not candidate.excluded or include_excluded:
            candidates.append(candidate)

    candidates.sort(key=lambda c: c.final_score, reverse=True)
    for i, c in enumerate(candidates):
        c.rank = i + 1

    result = candidates[:limit]

    query_id = store_query_batch(result, area)

    return result, query_id


def generate_candidates_from_polygon(
    polygon: list[list[list[float]]],
    profile_key: str = "regional_compute_5mw",
    scoring_profile_key: str = "default",
    limit: int = 25,
    include_excluded: bool = False,
    existing_infrastructure: dict[str, Any] | None = None,
) -> tuple[list[CandidateSite], str]:
    coords = polygon[0] if polygon else []
    if not coords:
        raise ValueError("Polygon must have at least one ring with coordinates")
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    bbox = (min(lons), min(lats), max(lons), max(lats))
    area = {"type": "polygon", "coordinates": polygon}
    candidates, query_id = generate_candidates_from_bbox(bbox, profile_key, scoring_profile_key, limit, include_excluded, existing_infrastructure)
    return candidates, query_id
