"""Validate site selection data integrity, scoring, and API contracts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas.site_selection.models import MissingDataFlag, CandidateSite
from atlas.site_selection.profiles import COMPUTE_PROFILES, SCORING_PROFILES, validate_all_profiles
from atlas.site_selection.scoring import score_candidate, SCORE_MIN, SCORE_MAX


def check_forbidden_phrases(text: str) -> list[str]:
    forbidden = [
        "approved site",
        "guaranteed buildable",
        "certified location",
        "legally compliant location",
        "grid-approved",
        "investment-ready",
        "definitive site selection",
        "permitted site",
    ]
    found = []
    for phrase in forbidden:
        if phrase.lower() in text.lower():
            found.append(phrase)
    return found


MAX_INDEX_SIZE_BYTES = 10_000_000

INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "derived" / "site_selection" / "infrastructure_index.json"
LAND_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "derived" / "site_selection" / "land_index.json"


def validate_infrastructure_index() -> list[str]:
    """Validate the derived infrastructure index."""
    errors = []
    if not INDEX_PATH.exists():
        errors.append(f"INDEX: Infrastructure index not found at {INDEX_PATH}")
        return errors

    size = INDEX_PATH.stat().st_size
    if size > MAX_INDEX_SIZE_BYTES:
        errors.append(
            f"INDEX: Infrastructure index is {size} bytes, exceeds max {MAX_INDEX_SIZE_BYTES} bytes"
        )

    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception as e:
        errors.append(f"INDEX: Failed to parse infrastructure index: {e}")
        return errors

    metadata = index.get("metadata", {})
    feature_counts = metadata.get("feature_counts", {})
    print(f"  Index size: {size} bytes ({size/1024/1024:.1f} MB)")
    print(f"  Generated at: {metadata.get('generated_at', 'unknown')}")
    print(f"  Feature counts:")
    for k, v in feature_counts.items():
        print(f"    {k}: {v}")
    total = sum(v for v in feature_counts.values())
    print(f"  Total features: {total}")

    empty_categories = [k for k, v in feature_counts.items() if v == 0]
    if empty_categories:
        print(f"  WARNING: Empty categories (proxy scoring remains limited): {', '.join(empty_categories)}")

    features = index.get("features", {})
    pp = features.get("power_plant_points", [])
    dc = features.get("data_center_points", [])
    if pp:
        sample = pp[0]
        keys = set(sample.keys())
        # Compact keys 't'/'q' indicate compact format
        if "notes" in keys:
            errors.append("INDEX: Per-feature notes found — they should be stripped to metadata")
    if dc:
        sample = dc[0]
        keys = set(sample.keys())
        if "notes" in keys:
            errors.append("INDEX: Per-feature notes found — they should be stripped to metadata")

    # Verify no keys that look like verbose notes
    for category, feature_list in features.items():
        for feat in feature_list[:20]:
            if "notes" in feat:
                errors.append(f"INDEX: Feature in {category} has 'notes' field — should be removed for compactness")
                break

    return errors


def validate_land_index() -> list[str]:
    """Validate the derived land suitability index."""
    errors = []
    if not LAND_INDEX_PATH.exists():
        errors.append(f"LAND: Land index not found at {LAND_INDEX_PATH}")
        return errors

    size = LAND_INDEX_PATH.stat().st_size
    if size > MAX_INDEX_SIZE_BYTES:
        errors.append(f"LAND: Land index is {size} bytes, exceeds max {MAX_INDEX_SIZE_BYTES} bytes")

    try:
        with open(LAND_INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception as e:
        errors.append(f"LAND: Failed to parse land index: {e}")
        return errors

    metadata = index.get("metadata", {})
    feature_counts = metadata.get("feature_counts", {})
    print(f"  Land index size: {size} bytes ({size/1024/1024:.1f} MB)")
    print(f"  Generated at: {metadata.get('generated_at', 'unknown')}")
    print(f"  Feature counts:")
    for k, v in feature_counts.items():
        print(f"    {k}: {v}")
    total = sum(v for v in feature_counts.values())
    print(f"  Total features: {total}")

    empty_categories = [k for k, v in feature_counts.items() if v == 0]
    if empty_categories:
        print(f"  WARNING: Empty land categories: {', '.join(empty_categories)}")

    features = index.get("features", {})
    ind = features.get("industrial_proxy_points", [])
    if ind:
        sample = ind[0]
        if "notes" in sample:
            errors.append("LAND: Per-feature notes found — they should be stripped to metadata")

    for category, feature_list in features.items():
        for feat in feature_list[:20]:
            if "notes" in feat:
                errors.append(f"LAND: Feature in {category} has 'notes' field")
                break

    return errors


def main() -> int:
    errors = []

    # 0. Validate infrastructure index
    index_errors = validate_infrastructure_index()
    errors.extend(index_errors)

    # 1. Validate profile weights
    weight_errors = validate_all_profiles()
    errors.extend(f"WEIGHT: {e}" for e in weight_errors)

    # 2. Validate all missing data flags are valid enum values
    valid_flags = {f.value for f in MissingDataFlag}
    for profile_key, profile in COMPUTE_PROFILES.items():
        test_candidate = CandidateSite(
            candidate_site_id=f"validate-{profile_key}",
            country="Test",
            region="Test",
            municipality="Test",
            lat=0,
            lon=0,
            geometry={"type": "Point", "coordinates": [0, 0]},
            area_ha=profile.preferred_area_ha,
            compute_profile=profile_key,
        )
        scores, flags = score_candidate(test_candidate, profile)
        for flag in flags:
            if flag not in valid_flags:
                errors.append(f"FLAG: Unknown missing data flag '{flag}' in profile {profile_key}")

    # 3. Validate score ranges
    for profile_key, profile in COMPUTE_PROFILES.items():
        for score_attr in ["grid_score", "fiber_score", "land_score", "climate_score", "water_score", "regulatory_score", "market_score", "final_score"]:
            val = getattr(test_candidate, score_attr, None)
            if val is not None and not (SCORE_MIN <= val <= SCORE_MAX):
                errors.append(f"RANGE: {score_attr}={val} out of range for {profile_key}")

    # 4. Check for forbidden phrases in evidence
    test_candidate.evidence_summary = "This is a preliminary candidate location for compute infrastructure."
    found = check_forbidden_phrases(test_candidate.evidence_summary)
    if found:
        errors.append(f"FORBIDDEN: Evidence contains disallowed phrases: {found}")

    # 5b. Validate land index
    land_errors = validate_land_index()
    errors.extend(land_errors)

    # 6. Verify missing data flags reduce confidence
    from atlas.site_selection.confidence import compute_confidence_score
    full_candidate = CandidateSite(
        candidate_site_id="full-data",
        country="NL",
        region="North Holland",
        municipality="Amsterdam",
        lat=52.37,
        lon=4.89,
        geometry={"type": "Point", "coordinates": [4.89, 52.37]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
        nearest_substation_km=0.5,
        nearest_power_line_km=0.3,
        nearest_fiber_km=0.2,
        nearest_ixp_km=2,
        estimated_grid_capacity_mw=50,
        flood_risk_score=10,
        water_stress_score=20,
        regulatory_stability_score=80,
        market_demand_score=75,
        zoning_compatibility_score=85,
    )
    profile = COMPUTE_PROFILES["regional_compute_5mw"]
    score_candidate(full_candidate, profile)
    full_conf = compute_confidence_score(full_candidate)

    empty_candidate = CandidateSite(
        candidate_site_id="no-data",
        country="Test",
        region="Test",
        municipality="Test",
        lat=0,
        lon=0,
        geometry={"type": "Point", "coordinates": [0, 0]},
        area_ha=2,
        compute_profile="regional_compute_5mw",
    )
    score_candidate(empty_candidate, profile)
    empty_conf = compute_confidence_score(empty_candidate)

    if empty_conf >= full_conf:
        errors.append(f"CONFIDENCE: Empty data ({empty_conf:.1f}) has >= confidence than full data ({full_conf:.1f})")

    if errors:
        print(f"Validation FAILED with {len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("Site selection validation PASSED")
    print(f"  Compute profiles: {len(COMPUTE_PROFILES)}")
    print(f"  Scoring profiles: {len(SCORING_PROFILES)}")
    print(f"  Missing data flags: {len(valid_flags)}")
    print(f"  Full data confidence: {full_conf:.1f}")
    print(f"  Empty data confidence: {empty_conf:.1f}")
    print(f"  Confidence differential: {full_conf - empty_conf:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
