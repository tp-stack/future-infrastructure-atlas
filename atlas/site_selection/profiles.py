"""Compute profiles and scoring profiles for site selection."""

from __future__ import annotations

from atlas.site_selection.models import ComputeProfile, ScoringProfile

COMPUTE_PROFILES: dict[str, ComputeProfile] = {
    "edge_ai_node_1mw": ComputeProfile(
        key="edge_ai_node_1mw",
        name="Edge AI Node (1 MW)",
        description="Small-scale edge AI inference node suitable for local low-latency processing near data sources.",
        min_power_mw=1,
        preferred_area_ha=0.5,
        max_substation_distance_km=5,
        max_fiber_distance_km=2,
        latency_priority="high",
        grid_priority="medium",
        regulatory_priority="medium",
        typical_use_case="Edge AI inference, IoT processing, local model serving",
        min_area_ha=0.1,
    ),
    "regional_compute_5mw": ComputeProfile(
        key="regional_compute_5mw",
        name="Regional Compute (5 MW)",
        description="Medium-scale regional compute pod for cloud edge zones and enterprise workloads.",
        min_power_mw=5,
        preferred_area_ha=2,
        max_substation_distance_km=10,
        max_fiber_distance_km=5,
        latency_priority="medium",
        grid_priority="high",
        regulatory_priority="medium",
        typical_use_case="Cloud edge zones, enterprise AI workloads, regional HPC",
        min_area_ha=0.5,
    ),
    "sovereign_compute_campus_20mw": ComputeProfile(
        key="sovereign_compute_campus_20mw",
        name="Sovereign Compute Campus (20 MW)",
        description="Large sovereign AI compute campus with high regulatory, data sovereignty and grid requirements.",
        min_power_mw=20,
        preferred_area_ha=8,
        max_substation_distance_km=15,
        max_fiber_distance_km=10,
        latency_priority="medium",
        grid_priority="very_high",
        regulatory_priority="very_high",
        typical_use_case="Sovereign AI cloud, national compute infrastructure, regulated data processing",
        min_area_ha=2,
    ),
    "hyperscale_ai_campus_100mw": ComputeProfile(
        key="hyperscale_ai_campus_100mw",
        name="Hyperscale AI Campus (100 MW)",
        description="Ultra-large hyperscale AI training campus requiring extreme grid capacity, land area and fiber diversity.",
        min_power_mw=100,
        preferred_area_ha=30,
        max_substation_distance_km=25,
        max_fiber_distance_km=15,
        latency_priority="medium",
        grid_priority="extreme",
        regulatory_priority="high",
        typical_use_case="Hyperscale AI training, foundation model clusters, large-scale HPC",
        min_area_ha=5,
    ),
}

SCORING_PROFILES: dict[str, ScoringProfile] = {
    "default": ScoringProfile(
        key="default",
        name="Default Scoring",
        description="Balanced scoring weights optimized for general compute site selection.",
        weights={
            "grid_score": 0.30,
            "fiber_score": 0.20,
            "land_score": 0.15,
            "climate_score": 0.10,
            "regulatory_score": 0.10,
            "market_score": 0.10,
            "incentive_score": 0.05,
        },
        confidence_weights={
            "data_completeness_score": 0.45,
            "source_quality_score": 0.30,
            "freshness_score": 0.15,
            "spatial_precision_score": 0.10,
        },
    ),
    "future_sovereign_compute": ScoringProfile(
        key="future_sovereign_compute",
        name="Future Sovereign Compute",
        description="Weights favoring regulatory stability, data sovereignty and grid capacity for sovereign AI infrastructure.",
        weights={
            "grid_score": 0.30,
            "fiber_score": 0.18,
            "land_score": 0.12,
            "climate_score": 0.08,
            "regulatory_score": 0.17,
            "market_score": 0.10,
            "incentive_score": 0.05,
        },
        confidence_weights={
            "data_completeness_score": 0.45,
            "source_quality_score": 0.30,
            "freshness_score": 0.15,
            "spatial_precision_score": 0.10,
        },
    ),
}


def validate_weights(weights: dict[str, float]) -> bool:
    total = sum(weights.values())
    return abs(total - 1.0) < 0.001


def validate_all_profiles() -> list[str]:
    errors = []
    for key, profile in SCORING_PROFILES.items():
        if not validate_weights(profile.weights):
            errors.append(f"Scoring profile '{key}' weights sum to {sum(profile.weights.values()):.4f}, expected 1.0")
    return errors
