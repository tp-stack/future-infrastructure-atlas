#!/usr/bin/env python3
"""Audit site selection data sources to determine usability for scoring."""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple

def audit_file(filepath: Path) -> Dict[str, Any]:
    """Audit a single file and return metadata."""
    result = {
        "path": str(filepath),
        "exists": filepath.exists(),
        "size_bytes": 0,
        "file_type": "unknown",
        "is_geojson": False,
        "feature_count": 0,
        "contains_coordinates": False,
        "contains_voltage": False,
        "contains_country": False,
        "contains_city_or_municipality": False,
        "contains_geometry": False,
        "safe_for_runtime_load": False,
        "safe_for_derived_index": False,
        "classification": "unknown_or_unsupported",
        "notes": ""
    }
    
    if not result["exists"]:
        result["notes"] = "File does not exist"
        return result
    
    try:
        result["size_bytes"] = filepath.stat().st_size
    except Exception as e:
        result["notes"] = f"Error getting size: {e}"
        return result
    
    # Determine file type
    if filepath.suffix == ".geojson":
        result["file_type"] = "GeoJSON"
        result["is_geojson"] = True
    elif filepath.suffix == ".json":
        result["file_type"] = "JSON"
    elif filepath.suffix == ".csv":
        result["file_type"] = "CSV"
    else:
        result["file_type"] = filepath.suffix[1:] if filepath.suffix else "unknown"
        result["notes"] = f"Unsupported file extension: {filepath.suffix}"
        return result
    
    # Try to read and parse the file
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            if filepath.suffix == ".geojson" or filepath.suffix == ".json":
                data = json.load(f)
            else:
                # For CSV, we'll just read the first few lines
                lines = [next(f) for _ in range(5)]
                data = lines
    except Exception as e:
        result["notes"] = f"Error parsing file: {e}"
        result["classification"] = "unknown_or_unsupported"
        return result
    
    # Analyze based on file type
    if result["is_geojson"]:
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            features = data.get("features", [])
            result["feature_count"] = len(features)
            if result["feature_count"] > 0:
                # Check first feature for properties
                first_feature = features[0]
                if isinstance(first_feature, dict):
                    props = first_feature.get("properties", {})
                    result["contains_coordinates"] = "geometry" in first_feature and first_feature["geometry"] is not None
                    # Check for specific properties
                    for key in props:
                        if key.lower() in ["voltage", "kv"]:
                            result["contains_voltage"] = True
                        if key.lower() in ["country", "c"]:
                            result["contains_country"] = True
                        if key.lower() in ["city", "municipality", "m", "region", "r"]:
                            result["contains_city_or_municipality"] = True
                    result["contains_geometry"] = result["contains_coordinates"]
                    
                    # Determine classification
                    if result["size_bytes"] < 5 * 1024 * 1024:  # Less than 5 MB
                        result["safe_for_runtime_load"] = True
                        result["safe_for_derived_index"] = True
                        if result["feature_count"] > 0:
                            result["classification"] = "usable_small_feature_file"
                        else:
                            result["classification"] = "empty_feature_collection"
                    else:
                        result["safe_for_runtime_load"] = False
                        result["safe_for_derived_index"] = True  # Can still be used to build derived index
                        result["classification"] = "large_raw_source_for_preprocessing_only"
                        result["notes"] = f"File is large ({result['size_bytes']} bytes), consider preprocessing"
                else:
                    result["notes"] = "First feature is not a dict"
                    result["classification"] = "unknown_or_unsupported"
            else:
                result["classification"] = "empty_feature_collection"
                result["notes"] = "FeatureCollection has 0 features"
        else:
            result["notes"] = "Not a FeatureCollection"
            result["classification"] = "unknown_or_unsupported"
    elif filepath.suffix == ".json":
        # Handle JSON files that are not GeoJSON
        if isinstance(data, dict):
            result["safe_for_runtime_load"] = result["size_bytes"] < 5 * 1024 * 1024
            result["safe_for_derived_index"] = True
            if result["size_bytes"] < 5 * 1024 * 1024:
                result["classification"] = "usable_small_feature_file"
            else:
                result["classification"] = "large_raw_source_for_preprocessing_only"
                result["notes"] = f"File is large ({result['size_bytes']} bytes), consider preprocessing"
            # Check for known array keys that contain features
            known_array_keys = ["power_plants", "data_centers", "cables", "facilities", "landing_stations", "substations"]
            found_arrays = []
            total_feature_count = 0
            for key in known_array_keys:
                arr = data.get(key)
                if isinstance(arr, list):
                    count = len(arr)
                    total_feature_count += count
                    found_arrays.append(f"{key}: {count}")
                    # Sample first record to detect fields
                    if count > 0 and isinstance(arr[0], dict):
                        record = arr[0]
                        if "lat" in record and "lon" in record:
                            result["contains_coordinates"] = True
                        if any(k in record for k in ("country", "c", "iso_country", "country_code")):
                            result["contains_country"] = True
                        if any(k in record for k in ("city", "municipality", "m", "region", "r")):
                            result["contains_city_or_municipality"] = True
            if found_arrays:
                result["feature_count"] = total_feature_count
                arr_detail = "; ".join(found_arrays)
                existing = result.get("notes", "")
                result["notes"] = (existing + "; " if existing else "") + f"Array counts: {arr_detail}"
        else:
            result["notes"] = "JSON root is not an object"
            result["classification"] = "unknown_or_unsupported"
    elif filepath.suffix == ".csv":
        # For CSV, we'll just note it's likely a raw source
        result["safe_for_runtime_load"] = False  # CSV can be large, we'll not load per request
        result["safe_for_derived_index"] = True
        if result["size_bytes"] < 5 * 1024 * 1024:
            result["classification"] = "usable_small_feature_file"
        else:
            result["classification"] = "large_raw_source_for_preprocessing_only"
            result["notes"] = f"File is large ({result['size_bytes']} bytes), consider preprocessing"
        # We'll assume it contains coordinates unless we can check quickly
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
                if "lat" in header.lower() and "lon" in header.lower():
                    result["contains_coordinates"] = True
        except Exception:
            pass
    else:
        result["notes"] = f"Unsupported file type: {result['file_type']}"
        result["classification"] = "unknown_or_unsupported"
    
    return result

def main():
    """Main audit function."""
    # Define paths to audit
    base_dir = Path(__file__).parent.parent
    paths_to_audit = [
        # Frontend public data
        base_dir / "frontend" / "public" / "data",
        # Processed data
        base_dir / "data" / "processed",
        # Raw data
        base_dir / "data" / "raw",
        # Derived data (if exists)
        base_dir / "data" / "derived",
    ]
    
    # Specific files we know about from the context
    specific_files = [
        base_dir / "frontend" / "public" / "data" / "atlas_core.json",
        base_dir / "frontend" / "public" / "data" / "atlas_web_data.json",
        base_dir / "frontend" / "public" / "data" / "power_lines.json",
        base_dir / "frontend" / "public" / "data" / "substations.json",
        base_dir / "frontend" / "public" / "data" / "openinframap_power_extract.json",
        base_dir / "data" / "processed" / "web" / "atlas_web_data.json",
        base_dir / "data" / "processed" / "global_datacenters_public_peeringdb.csv",
        base_dir / "data" / "raw" / "wri_global_power_plants" / "manual_20260511" / "global_power_plant_database_wri_all.csv",
        base_dir / "data" / "raw" / "wri_global_power_plants" / "manual_20260511" / "wri_global_power_plants_1000_records.csv",
        base_dir / "data" / "raw" / "peeringdb" / "facilities_raw.json",
        base_dir / "data" / "raw" / "submarine_cable_geometries" / "kmcd_manual_20260511" / "all_cables.json",
        base_dir / "data" / "raw" / "submarine_cable_geometries" / "kmcd_manual_20260511" / "world_submarine_cable_geometries_kmcd.csv",
        base_dir / "data" / "raw" / "submarine_cable_lines" / "manual_20260511" / "global_submarine_cable_lines_scn_segments.csv",
        base_dir / "data" / "raw" / "submarine_cable_lines" / "manual_20260511" / "world_submarine_cable_segments_public_research_full.csv",
    ]
    
    # Audit specific files
    results = []
    for filepath in specific_files:
        if filepath.exists():
            results.append(audit_file(filepath))
    
    # Also audit directories to catch any other files
    for dir_path in paths_to_audit:
        if dir_path.exists() and dir_path.is_dir():
            for ext in ["*.geojson", "*.json", "*.csv"]:
                for filepath in dir_path.rglob(ext):
                    # Avoid duplicates
                    if filepath not in [r["path"] for r in results if "path" in r]:
                        results.append(audit_file(filepath))
    
    # Sort results by path for consistent output
    results.sort(key=lambda x: x["path"])
    
    # Output to JSON
    output_path = base_dir / "data" / "reports" / "site_selection" / "source_audit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print(f"Audit complete. Results written to: {output_path}")
    print("\nSummary:")
    classifications = {}
    for r in results:
        c = r.get("classification", "unknown")
        classifications[c] = classifications.get(c, 0) + 1
    for classification, count in classifications.items():
        print(f"  {classification}: {count}")
    
    # Print details for files that are usable or large raw sources
    print("\nDetails:")
    for r in results:
        if r["classification"] in ["usable_small_feature_file", "large_raw_source_for_preprocessing_only", "empty_feature_collection"]:
            print(f"  {r['path']}:")
            print(f"    Classification: {r['classification']}")
            print(f"    Size: {r['size_bytes']} bytes")
            print(f"    Feature count: {r.get('feature_count', 0)}")
            if r["notes"]:
                print(f"    Notes: {r['notes']}")

if __name__ == "__main__":
    main()