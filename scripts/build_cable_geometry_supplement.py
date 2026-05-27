"""
Build supplemental cable geometry lookup: fuzzy name bridge + schematic geometries.
Only includes verified correct matches.
"""
import csv, json, re
from pathlib import Path

BASE = Path(r'C:\Users\rperi\Geo\future-infrastructure-atlas')

import unicodedata

def _normalize_key(name):
    n = name.strip().lower()
    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
    n = re.sub(r'[^a-z0-9]', '_', n)
    n = re.sub(r'_+', '_', n)
    return n.strip('_')

# Load KMCD CSV
kmcd_by_name = {}
with open(BASE / 'data' / 'raw' / 'submarine_cable_geometries' / 'kmcd_manual_20260511' / 'world_submarine_cable_geometries_kmcd.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        name = (row.get('cable_name') or '').strip()
        if not name: continue
        key = _normalize_key(name)
        if key not in kmcd_by_name:
            kmcd_by_name[key] = row

# Fuzzy match mapping: SCN normalized_key -> KMCD normalized_key (manual verified)
fuzzy_mapping = {
    'asia_submarine_cable_express_asecahaya_malaysia': 'asia_submarine_cable_express_ase_cahaya_malaysia',
    'b2js_jakarta_bangka_batam_singapore_cable_system': 'jakarta_bangka_batam_singapore_b2js',
    'batam_dumai_melaka_bdm_cable_system': 'batam_dumai_melaka_bdm',
    'chennai_andaman_nicobar_islands_cable': 'chennai_andaman_nicobar_islands_cable_cani',
    'cross_straits_cable_network': 'cross_straits_cable_network_cscn',
    'djibouti_africa_regional_express_1_dare1': 'djibouti_africa_regional_express_1_dare_1',
    'dumai_melaka_cable_system': 'dumai_melaka_cable_system_dmcs',
    'eastern_light': 'eastern_light_sweden_finland_i',
    'fibra_optica_al_pacifico': 'fibra_optica_al_pacifico',
    'finland_estonia_connection_fec': 'finland_estonia_connection_1_fec_1',
    'flag_north_asia_loopreach_north_asia_loop': 'flag_north_asia_loop_reach_north_asia_loop',
    'gulf_bridge_international_cable_system_gbicsmiddle_east_north_africa_mena_cable_system': 'gulf_bridge_international_cable_system_middle_east_north_africa_cable_system_gbics_mena',
    'havhingstennorth_sea_connect_nsc': 'havhingsten_north_sea_connect_nsc',
    'hics_hawaii_inter_island_cable_system': 'hawaii_inter_island_cable_system_hics',
    'hifn_hawaii_island_fibre_network': 'hawaii_island_fibre_network_hifn',
    'italy_greece_1': 'italy_greece_1_ig_1',
    'middle_east_north_africa_mena_cable_systemgulf_bridge_international': 'middle_east_north_africa_mena_cable_system_gulf_bridge_international',
    'sape_labuanbajo_ende_kupang_cable_systems': 'sape_labuan_bajo_ende_kupang',
    'sir_abu_nuayr_cable': 'sir_abu_nuayr_cable',
    'south_pacific_cable_system_spscmistral': 'south_pacific_cable_system_spcs_mistral',
    'tanjun_pandan_sungai_kakap_cable_system': 'tanjung_pandan_sungai_kakap',
    'trans_adriatic_express': 'trans_adriatic_express_tae',
}

supplement = {}
for scn_key, kmcd_key in sorted(fuzzy_mapping.items()):
    if kmcd_key not in kmcd_by_name:
        print(f'  KMCD key not found: {kmcd_key}')
        continue
    row = kmcd_by_name[kmcd_key]
    geom_json = row.get('geometry_json', '{}')
    try:
        geom = json.loads(geom_json)
    except:
        continue
    gtype = geom.get('type')
    coords = geom.get('coordinates', [])
    
    if gtype == 'LineString':
        valid = [(round(p[0], 1), round(p[1], 1)) for p in coords 
                 if isinstance(p, (list, tuple)) and len(p) >= 2 and -180 <= p[0] <= 180 and -90 <= p[1] <= 90]
        if len(valid) >= 2:
            supplement[scn_key] = {'geometry': valid, 'source': 'fuzzy_match_kmcd', 'precision': row.get('geometry_precision', 'generalized_public_geometry')}
    elif gtype == 'MultiLineString':
        cleaned = []
        for line in coords:
            valid_line = [(round(p[0], 1), round(p[1], 1)) for p in line 
                         if isinstance(p, (list, tuple)) and len(p) >= 2 and -180 <= p[0] <= 180 and -90 <= p[1] <= 90]
            if len(valid_line) >= 2:
                cleaned.append(valid_line)
        if cleaned:
            supplement[scn_key] = {'geometry': cleaned, 'source': 'fuzzy_match_kmcd', 'precision': row.get('geometry_precision', 'generalized_public_geometry')}

print(f'Fuzzy bridge: {len(supplement)} matched entries')

# Load and add schematic geometries
schematic_path = BASE / 'config' / 'cable_schematic_geometries.json'
if schematic_path.exists():
    with open(schematic_path) as f:
        schematic = json.load(f)
    for key, geom in schematic.items():
        if key not in supplement:
            supplement[key] = {'geometry': geom, 'source': 'schematic_landing_points', 'precision': 'schematic_landing_points'}
    print(f'Schematic geometries: {len(schematic)} entries')

print(f'Total supplemental geometries: {len(supplement)}')

# Save
output = BASE / 'config' / 'cable_geometry_supplement.json'
with open(output, 'w') as f:
    json.dump(supplement, f, indent=2)
print(f'Saved to {output}')
