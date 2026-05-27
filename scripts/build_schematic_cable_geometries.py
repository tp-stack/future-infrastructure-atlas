"""
Build schematic geometries for submarine cables that lack KMCD geometry.
Extracts landing point coordinates from KMCD cable endpoints.
Generates connect-the-dots LineStrings between landing points for unmatched cables.
"""
import csv, json, re, math, sys
from pathlib import Path

BASE = Path(r'C:\Users\rperi\Geo\future-infrastructure-atlas')

def _normalize_key(name):
    n = name.strip().lower()
    n = re.sub(r'[^a-z0-9]', '_', n)
    n = re.sub(r'_+', '_', n)
    return n.strip('_')

# ── Step 1: Build landing point coordinate lookup from KMCD geometry ──
def extract_landing_point_coords() -> dict[str, tuple[float, float]]:
    """Extract approximate landing point coordinates from KMCD cable geometries.
    For each cable with landing_points_json, associate the first and last
    coordinate of each geometry segment with landing point names."""
    lp_coords: dict[str, list[tuple[float, float]]] = {}
    
    with open(BASE / 'data' / 'raw' / 'submarine_cable_geometries' / 'kmcd_manual_20260511' / 'world_submarine_cable_geometries_kmcd.csv', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get('cable_name') or '').strip()
            geom_json = row.get('geometry_json', '{}')
            lp_json = row.get('landing_points_json', '[]')
            try:
                geom = json.loads(geom_json)
                lps = json.loads(lp_json)
            except:
                continue
            if not isinstance(lps, list) or not lps:
                continue
            
            # Extract endpoints of this cable's geometry
            endpoints = []
            gtype = geom.get('type')
            coords = geom.get('coordinates', [])
            if gtype == 'LineString':
                if len(coords) >= 2:
                    endpoints.append(tuple(coords[0]))
                    endpoints.append(tuple(coords[-1]))
            elif gtype == 'MultiLineString':
                for line in coords:
                    if len(line) >= 2:
                        endpoints.append(tuple(line[0]))
                        endpoints.append(tuple(line[-1]))
            
            if not endpoints:
                continue
            
            # Assign coordinates to landing point names
            # We match by index: first lp -> first endpoint, last lp -> last endpoint
            # For intermediate lps, interpolate
            for i, lp in enumerate(lps):
                lp_name = lp.get('name', '')
                if not lp_name:
                    continue
                lp_key = lp_name.lower().strip()
                # Find closest endpoint
                if i < len(endpoints):
                    pt = endpoints[i]
                else:
                    pt = endpoints[-1]
                if lp_key not in lp_coords:
                    lp_coords[lp_key] = []
                lp_coords[lp_key].append(pt)
    
    # Average coordinates for each landing point
    result = {}
    for name, points in lp_coords.items():
        avg_lon = sum(p[0] for p in points) / len(points)
        avg_lat = sum(p[1] for p in points) / len(points)
        result[name] = (round(avg_lon, 4), round(avg_lat, 4))
    
    return result

# ── Step 2: Parse SCN landing points text ──
def parse_scn_landing_points(text: str) -> list[str]:
    """Parse SCN landing points field into a list of city/country names."""
    if not text:
        return []
    parts = re.split(r'\s*\|\s*', text)
    return [p.strip() for p in parts if p.strip()]

def parse_segment_endpoints(text: str) -> list[str]:
    """Parse SCN segment_endpoints field into endpoint name pairs."""
    if not text:
        return []
    parts = re.split(r'\s*;\s*', text)
    return [p.strip() for p in parts if p.strip()]

# ── Step 3: Generate schematic geometry ──
def generate_schematic_geometry(
    landing_point_names: list[str],
    lp_coords: dict[str, tuple[float, float]]
) -> list | None:
    """Generate a LineString connecting landing points with known coordinates."""
    coords = []
    for lp_name in landing_point_names:
        # Try exact match first
        lp_key = lp_name.lower().strip()
        if lp_key in lp_coords:
            coords.append(list(lp_coords[lp_key]))
            continue
        # Try partial match (city name only)
        city = lp_name.split(',')[0].strip().lower()
        found = False
        for k, v in lp_coords.items():
            if city in k or k.split(',')[0].strip() == city:
                coords.append(list(v))
                found = True
                break
        if not found:
            # Try with the key normalized
            nlpk = _normalize_key(lp_name)
            for k, v in lp_coords.items():
                if _normalize_key(k) == nlpk:
                    coords.append(list(v))
                    found = True
                    break
        if not found:
            # Can't geocode this landing point
            pass
    
    if len(coords) >= 2:
        return coords  # Simple LineString
    return None

# ── Main ──
def main():
    print('Building landing point coordinate lookup from KMCD...')
    lp_coords = extract_landing_point_coords()
    print(f'  Found coordinates for {len(lp_coords)} landing points')
    
    # Load SCN cables
    scn_cables: dict[str, dict] = {}
    with open(BASE / 'data' / 'raw' / 'submarine_cable_lines' / 'manual_20260511' / 'global_submarine_cable_lines_scn_segments.csv', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = (row.get('cable_system_name') or '').strip()
            if not name: continue
            key = _normalize_key(name)
            if key not in scn_cables:
                scn_cables[key] = {
                    'n': name,
                    'landing_points': row.get('landing_points', ''),
                    'operators': row.get('operators', ''),
                    'length_km': row.get('system_length_km_raw', ''),
                    'segment_endpoints': row.get('segment_endpoints', row.get('segment_endpoints_raw', '')),
                }
    
    # Load KMCD keys
    kmcd_keys = set()
    with open(BASE / 'data' / 'raw' / 'submarine_cable_geometries' / 'kmcd_manual_20260511' / 'world_submarine_cable_geometries_kmcd.csv', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = (row.get('cable_name') or '').strip()
            if name:
                kmcd_keys.add(_normalize_key(name))
    
    # Also add fuzzy-matched keys
    fuzzy_matched_keys = {
        'asia_submarine_cable_express_asecahaya_malaysia',
        'b2js_jakarta_bangka_batam_singapore_cable_system',
        'batam_dumai_melaka_bdm_cable_system',
        'chennai_andaman_nicobar_islands_cable',
        'cross_straits_cable_network',
        'djibouti_africa_regional_express_1_dare1',
        'dumai_melaka_cable_system',
        'east_coast_cable_system',
        'eastern_light',
        'fibra_optica_al_pacifico',
        'finland_estonia_connection_fec',
        'flag_north_asia_loopreach_north_asia_loop',
        'gulf_bridge_international_cable_system_gbicsmiddle_east_north_africa_mena_cable_system',
        'havhingstennorth_sea_connect_nsc',
        'hics_hawaii_inter_island_cable_system',
        'hifn_hawaii_island_fibre_network',
        'italy_greece_1',
        'middle_east_north_africa_mena_cable_systemgulf_bridge_international',
        'sape_labuanbajo_ende_kupang_cable_systems',
        'seacomtata_tgn_eurasia',
        'sir_abu_nuayr_cable',
        'south_pacific_cable_system_spscmistral',
        'tanjun_pandan_sungai_kakap_cable_system',
        'tata_tgn_atlantic',
        'trans_adriatic_express',
        'trapani_kelibia',
    }
    
    # Find truly unmatched cables
    all_matched = kmcd_keys | fuzzy_matched_keys
    unmatched = {k: v for k, v in scn_cables.items() if k not in all_matched}
    print(f'\nTruly unmatched SCN cables: {len(unmatched)}')
    
    # Generate schematic geometries
    schematic_geometries = {}
    for key, cable in sorted(unmatched.items()):
        lp_names = parse_scn_landing_points(cable['landing_points'])
        if not lp_names:
            # Try segment_endpoints
            eps = parse_segment_endpoints(cable['segment_endpoints'])
            lp_names = []
            for ep in eps:
                parts = [p.strip() for p in ep.split(',')]
                if parts:
                    lp_names.append(parts[0])
        
        geom = generate_schematic_geometry(lp_names, lp_coords)
        if geom:
            schematic_geometries[key] = geom
            print(f'  GENERATED: "{cable["n"]}" ({len(geom)} pts from {len(lp_names)} landing pts)')
        else:
            print(f'  SKIPPED: "{cable["n"]}" (could not geocode enough landing points)')
    
    # Save schematic geometries
    output = BASE / 'config' / 'cable_schematic_geometries.json'
    with open(output, 'w') as f:
        json.dump(schematic_geometries, f, indent=2)
    print(f'\nSaved {len(schematic_geometries)} schematic geometries to {output}')

if __name__ == '__main__':
    main()
