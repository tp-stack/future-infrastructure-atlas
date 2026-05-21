# FUTURE Infrastructure Atlas

FUTURE Infrastructure Atlas is a global geospatial intelligence platform planned to map energy infrastructure, internet infrastructure, data centers, cloud regions, primary resources, water risk, and regional AI data center potential.

This repository currently contains the safe storage foundation, local PostGIS schema foundation, registry validation, and provenance manifest utilities. It does not ingest real datasets, generate vector tiles, or build a frontend yet.

## Storage Model

Large data files are never committed to Git. The repository stores code, configuration, documentation, SQL schemas, tiny test fixtures, and metadata manifests only.

Local datasets belong under `data/`:

- `data/raw/` for immutable source downloads
- `data/staging/` for temporary normalized extracts
- `data/processed/` for reproducible derived datasets
- `data/tiles/` for generated tile packages
- `data/cache/` for disposable local caches
- `data/reports/` for generated local reports
- `data/logs/` for local logs

These directories are ignored by Git except for `.gitkeep` placeholders and `data/README.md`.

## Why Large Files Are Ignored

Geospatial files such as GeoPackage, shapefile components, rasters, vector tiles, DuckDB databases, Parquet extracts, PMTiles, and MBTiles can quickly exceed safe repository limits. Committing them can slow down clones, break CI, crash local tooling, or make the frontend and API unsafe to run.

The storage policy is defined in `config/storage.yaml`, and the Python guardrail lives in `atlas/storage.py`.

## Initialize Local Storage

```powershell
python scripts/init_storage.py
```

or:

```powershell
make init-storage
```

## Run Tests

```powershell
pytest -q
```

or:

```powershell
make test
```

To run only the repository file safety check:

```powershell
make check-storage
```

## Agent Memory

This repo includes optional local `agentmemory` setup for Codex MCP sessions. It stores concise engineering lessons only; raw data, secrets, and restricted source material must not be saved to memory.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_agentmemory.ps1
```

Details are in `docs/agentmemory.md`.

## Step 2: Local PostGIS Foundation

Step 2 adds a local PostGIS database for normalized metadata and geospatial asset records. Raw source files still stay in `data/raw/` locally or in future object storage. The database is for structured dimensions, normalized infrastructure assets, relationships, ingestion logs, and regional scores.

Start PostGIS:

```powershell
docker compose up -d postgis
```

Initialize the schema and seed source registry:

```powershell
python scripts/init_db.py
```

Check database health:

```powershell
python scripts/check_db.py
```

Run all tests:

```powershell
pytest -q
```

The PostGIS integration tests skip automatically when the local database is unavailable. Real data ingestion, vector tile generation, API serving, and frontend work are not part of Step 2.

## Step 3: Registry And Provenance Foundation

Step 3 adds hardened source, dataset, and layer registries plus raw and ingestion manifest utilities. This step does not download, move, transform, or ingest real data.

The registry relationship is:

- `source` describes where data comes from and the license/access policy.
- `dataset` describes a specific future input tied to one source and one target layer.
- `layer` describes the public or enterprise map layer produced from one or more datasets.

Every future dataset must have registered provenance metadata before ingestion: source key, license, allowed usage, update frequency, sensitivity level, allowed precision, expected format, expected geometry or data type, and checksum requirements.

Validate registries:

```powershell
python scripts/check_registry.py
```

Create a sample raw manifest from the tiny test fixture:

```powershell
python scripts/create_manifest.py --dataset-key wri_global_power_plants --file-path tests/fixtures/sample_power_plants.csv --output data/cache/sample_power_plants.raw_manifest.json
```

Run tests:

```powershell
pytest -q
```

The sample manifest is written under `data/cache/`, which is ignored by Git. It is a local generated artifact, not a committed dataset or ingestion result.

## Step 4: Safe Fixture Ingestion Framework

Step 4 adds a safe fixture ingestion framework that validates, normalizes, and writes processed output for registered datasets without downloading real data or requiring external services.

The ingestion pipeline:

1. **Require dataset** registered in `config/datasets.yaml`
2. **Read CSV** from a local fixture file
3. **Create or require** raw provenance manifest via `atlas.provenance`
4. **Validate** required fields, latitude/longitude range, and data integrity
5. **Normalize** valid records into canonical JSONL with confidence metadata
6. **Write output** atomically to `data/processed/{dataset_key}/`
7. **Create manifest** with results, written to `data/cache/`
8. **Optionally load** to PostGIS if database is available

### Running Fixture Ingestion

Ingest the sample fixture:

```powershell
python scripts/ingest_dataset.py --dataset-key wri_global_power_plants --file-path tests/fixtures/sample_power_plants.csv
```

or:

```powershell
make ingest-test-fixture
```

### Normalized Output Structure

Each processed record contains:

```json
{
  "asset_type": "energy",
  "asset_subtype": "power_plant",
  "canonical_name": "Example Plant",
  "raw_name": "Example Plant",
  "country": "IT",
  "status": null,
  "confidence": 0.65,
  "sensitivity_level": "medium",
  "geometry_precision": "source_native",
  "longitude": 12.4924,
  "latitude": 41.8902,
  "properties": {
    "fuel_type": "solar",
    "capacity_mw": 10.5
  },
  "source_dataset_key": "wri_global_power_plants",
  "source_key": "wri_global_power_plant_database",
  "target_layer": "power_plants"
}
```

### Optional PostGIS Loading

Load processed records to PostGIS (skips gracefully if DB unavailable):

```powershell
python scripts/load_processed_to_postgis.py --processed-path data/processed/wri_global_power_plants/wri_global_power_plants.processed.jsonl --limit 10
```

or:

```powershell
make load-test-fixture-db
```

### Generated Files

All ingestion outputs are Git-ignored:

- **Processed output:** `data/processed/wri_global_power_plants/wri_global_power_plants.processed.jsonl`
- **Ingestion manifest:** `data/cache/wri_global_power_plants.ingestion_manifest.json`

### Testing

Run all tests including ingestion validators and fixture tests:

```powershell
pytest -q
```

DB tests skip automatically when PostGIS is unavailable. Tests verify:

- CSV column validation
- Latitude/longitude range validation
- Required field validation
- Normalized record structure
- Atomic output writing
- Git-safe output locations

### Safety Constraints

- No real datasets downloaded
- No real global data ingested
- All generated outputs in Git-ignored `data/` directories
- Fixture remains under 1 KB
- PostGIS optional and skips gracefully
- Storage safety policy preserved
```

or:

```powershell
make load-postgis
```

PostGIS loading is optional and skips gracefully if the database is unavailable.

All generated outputs are written to Git-ignored `data/` directories. No real datasets are downloaded, ingested, or committed.

## Step 5: Controlled WRI Power Plant Ingestion

Step 5 extends the ingestion framework to handle the real WRI Global Power Plant Database CSV format with field mapping, streaming support, and traceability fields.

The WRI dataset uses different column names than the sample fixture. A `field_map` in the dataset configuration maps WRI source columns to canonical field names (e.g. `primary_fuel` => `fuel_type`). This allows the required fields to remain stable across datasets.

**Key features:**
- **Field mapping** — WRI CSV columns (`primary_fuel`, `gppd_idnr`, `country_long`) are mapped to canonical names, with extra fields preserved in the normalized output
- **Streaming mode** — Large files are processed record-by-record without loading the full CSV into memory
- **Traceability** — WRI identifiers (`gppd_idnr`), owner, commissioning year, and country long name are preserved in each normalized record
- **Confidence** — Real WRI records get confidence 0.85 (vs 0.95 for the sample fixture)

**Manual download required:**
1. Download the WRI Global Power Plant Database CSV from https://datasets.wri.org/
2. Place it at `data/raw/wri_global_power_plants/global_power_plant_database.csv`

**Run controlled ingestion:**

```powershell
python scripts/ingest_dataset.py --dataset-key wri_global_power_plants --file-path data/raw/wri_global_power_plants/global_power_plant_database.csv
```

or:

```powershell
make ingest-wri
```

**Test with the WRI-format fixture:**

```powershell
python scripts/ingest_dataset.py --dataset-key wri_global_power_plants --file-path tests/fixtures/sample_wri_power_plants.csv
```

The WRI fixture has 3 rows: 2 valid, 1 with an invalid latitude (rejected during validation). PostGIS loading remains optional and skips gracefully when unavailable.

## Step 6: Deployable Global Infrastructure Map

Step 6 adds a deployable interactive map frontend and a Web data build pipeline.

### Raw CSV Placement

Place the real CSV files in the following Git-ignored locations:

- WRI Global Power Plant Database: `data/raw/wri_global_power_plants/manual_20260511/global_power_plant_database_wri_all.csv`
- Submarine cable lines: `data/raw/submarine_cable_lines/manual_20260511/global_submarine_cable_lines_scn_segments.csv`
- Frontier AI data centers: `data/raw/data_centers/manual_20260511/frontier_ai_data_centers_epoch_public.csv`

**Never commit raw CSV files.** They are already ignored by `.gitignore` under `data/raw/**`.

### Build Web Map Data

```powershell
python scripts/build_web_map_data.py --cable-geometry-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv --allow-license-review --max-public-mb 5
```

or:

```powershell
make build-map-data
```

This script:
1. Reads all three CSVs (streaming as needed)
2. Validates coordinates
3. Enriches submarine cables with the local KMCD geometry CSV for prototype/internal maps
4. Normalizes into compact frontend JSON
5. Writes to `frontend/public/data/atlas_web_data.json` if under 5 MB
6. Otherwise writes to `data/processed/web/atlas_web_data.json` and exits non-zero

**5 MB frontend payload limit:** If the generated JSON exceeds 5 MB, it is written to the Git-ignored `data/processed/web/` directory instead of `frontend/public/data/`. This prevents large data files from being committed to the repository.

**Prototype cable geometry:** The default `build-map-data` target uses `--allow-license-review` with the local KMCD geometry CSV. This is for internal/prototype use only until the KMCD/underlying cable geometry license is reviewed. Use `make build-map-data-legacy` to rebuild with only the small legacy lookup.

### Adding All Submarine Cables and Data Centers (Geospatial Sources)

The build pipeline supports source-backed ingestion of submarine cable geometries and data center coordinates from GeoJSON or CSV files, replacing the minimal lookup-based mapping with full geospatial coverage.

**Source file placement:**

GeoJSON files are auto-discovered under:
- `data/raw/submarine_cables/` for cables
- `data/raw/data_centers/` for data centers

Or provide explicit paths via `--cable-geo-path` and `--datacenter-geo-path`.

**Build with geospatial sources:**

```powershell
python scripts/build_web_map_data.py --cable-geo-path data/raw/submarine_cables/my_cables.geojson --datacenter-geo-path data/raw/data_centers/my_dcs.geojson --max-public-mb 5
```

**License review gate:**

All cable and data center sources are flagged `requires_license_review: true` in `config/sources.yaml` by default. Ingestion from licensed sources requires the `--allow-licensed-sources` flag:

```powershell
python scripts/build_web_map_data.py --cable-geo-path data/raw/submarine_cables/my_cables.geojson --allow-licensed-sources
```

Run without the flag to verify which sources trigger the gate.

**Fallback behavior:**

When no geospatial source files are found, the build falls back to the existing lookup-based mapping (`config/cable_geometries.json` and `config/datacenter_locations.yaml`), preserving the current mapped cables and data centers.

**Config files:**

- `config/sources.yaml` — source entries with `requires_license_review` flags
- `config/datasets.yaml` — dataset entries with accepted field aliases for GeoJSON properties
- `atlas/ingestion/geometry_utils.py` — coordinate parsing, validation, normalization
- `atlas/ingestion/geojson_loader.py` — load and normalize GeoJSON features
- `atlas/ingestion/cable_loader.py` — load cable geometries from GeoJSON
- `atlas/ingestion/datacenter_loader.py` — load data center coordinates from GeoJSON or CSV

**Tests:**

```powershell
pytest -q tests/test_geometry_utils.py tests/test_geojson_loader.py tests/test_cable_loader.py tests/test_datacenter_loader.py
```

### Adding Source-Backed Submarine Cable Geometries

The build pipeline supports loading cable geometries from a structured CSV derived from the **KMCD Internet Infrastructure Map** GeoJSON dataset, which contains 693 cable features with LineString and MultiLineString geometries.

**Source URL:** https://map.kmcd.dev/data/all_cables.json

**License status:** `to_verify` — requires license review before production/commercial use. The source page cites TeleGeography and Submarine Networks. Use for internal/prototype only until license is verified.

**Generate the geometry CSV:**

```powershell
python scripts/fetch_and_build_cable_geometry_csv.py --output-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv
```

Or from a local GeoJSON file:

```powershell
python scripts/fetch_and_build_cable_geometry_csv.py --input-geojson data/raw/submarine_cable_geometries/kmcd_manual_20260511/all_cables.json --output-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv
```

**Build map data with cable geometries:**

```powershell
python scripts/build_web_map_data.py --cable-geometry-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv --allow-license-review --max-public-mb 5
```

**Validate:**

```powershell
python scripts/check_frontend_data.py
```

**License review gate:** The CSV includes `license_review_required=true` and `source_license=to_verify`. The build script requires `--allow-license-review` to proceed. Without it, the build exits with:

> Cable geometry source requires license review. Re-run with --allow-license-review only for internal/prototype use.

**Pipeline summary:**

1. `fetch_and_build_cable_geometry_csv.py` — downloads/reads KMCD GeoJSON, validates geometry, strips altitude, produces CSV with 693 rows
2. `build_web_map_data.py --cable-geometry-csv ... --allow-license-review` — reads CSV, enriches cable inventory with geometry, produces `atlas_web_data.json`
3. Frontend MapLibre GeoJSON layers draw LineString and MultiLineString geometries in cyan

**Tests:**

```powershell
pytest -q tests/test_cable_geometry_build.py
```

### Frontend Install

```powershell
make frontend-install
```

### Frontend Development

```powershell
make frontend-dev
```

Then open http://localhost:5173 in a browser.

### Frontend Build

```powershell
make frontend-build
```

### Frontend Preview

```powershell
make frontend-preview
```

### Deploy to Vercel

```powershell
make deploy-vercel
```

If the Vercel CLI is not installed:

```powershell
npm install -g vercel
vercel login
cd frontend
vercel --prod
```

### Frontend Map

The default map uses:
- React + TypeScript + Vite
- MapLibre GL JS with a light topographic basemap
- GeoJSON sources loaded from `frontend/public/data/atlas_web_data.json`
- Power plant points colored by fuel type (amber/orange theme)
- Data center points in deep blue
- Submarine cable lines in blue
- Layer toggles, fuel/country/capacity filters
- Click popups with asset details
- Stats panel (loaded counts, rejected records)
- Source attribution and disclaimer panel
- Dark atlas controls over a light, readable map

### Safety Warnings

- Never commit raw CSVs or large generated data files
- Always verify `git status` before committing
- The build script enforces a 5 MB limit on frontend data
- If the limit is exceeded, data goes to `data/processed/web/` (Git-ignored)
- Test before deploying: `python scripts/build_web_map_data.py --cable-geometry-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv --allow-license-review --max-public-mb 5`

### Optional PMTiles Vector Tile Architecture

The stable default map is MapLibre rendering GeoJSON from `atlas_web_data.json`. PMTiles are optional future performance infrastructure and should not be treated as the baseline until `.pmtiles` files exist and the Tippecanoe build path is reliable.

- **Default renderer** - MapLibre GeoJSON sources loaded from `atlas_web_data.json`
- **Canvas fallback** - disabled by default and available only from the diagnostics panel
- **PMTiles vector tiles** - optional MapLibre vector tile layers built with Tippecanoe, loaded via the `pmtiles` protocol

`atlas_core.json` (~3 KB) is a metadata-only file. It contains counts, sources, disclaimers, a tile registry with per-layer URLs and status, license warnings, and data gaps. No heavy coordinate arrays are included.

#### Build atlas_core.json

```powershell
python scripts/build_atlas_core.py
```

or:

```powershell
make build-atlas-core
```

Requires `frontend/public/data/atlas_web_data.json` (generated by `build_web_map_data.py`).

#### Generate PMTiles

```powershell
python scripts/build_pmtiles.py --all --max-public-mb 25
```

or:

```powershell
make build-pmtiles
```

This script:
1. Reads `atlas_web_data.json`
2. Generates NDJSON feature files for 3 layers (power_plants, submarine_cables, data_centers) in `data/cache/pmtiles/`
3. Runs `tippecanoe` to produce `.pmtiles` files in `frontend/public/tiles/`
4. If a PMTiles exceeds 25 MB, it is moved to `data/tiles/` (Git-ignored) with instructions for object storage

**Tippecanoe is required.** On Windows, install via WSL, Docker, or Ubuntu. The script exits gracefully with install instructions if `tippecanoe` is not found.

#### Validate atlas_core.json

```powershell
python scripts/check_atlas_core.py
```

or:

```powershell
make check-atlas-core
```

#### How It Works

1. `App.tsx` fetches `atlas_core.json` for metadata only, then loads `atlas_web_data.json`
2. `AtlasMap.tsx` builds one MapLibre style with the light topographic basemap and GeoJSON infrastructure layers
3. Missing PMTiles never change the default renderer
4. The canvas overlay (`InfrastructureCanvasOverlay`) is available from diagnostics as a fallback/proof layer
5. `SourcePanel.tsx` and `StatsPanel.tsx` show cable geometry source and license-review status

#### Frontend Files

- `frontend/src/map/AtlasMap.tsx` - default MapLibre GeoJSON renderer
- `frontend/src/App.tsx` - loads `atlas_core.json` as metadata and `atlas_web_data.json` as the render source
- `frontend/src/map/pmtiles.ts` - optional PMTiles protocol registration and source/layer definitions for later use

#### Tests

```powershell
pytest -q tests/test_build_web_map_data.py
pytest -q tests/test_build_atlas_core.py
pytest -q tests/test_build_pmtiles_inputs.py
```

#### PMTiles Experiment

The previous `?pmtilesMap=1` route is no longer part of the stable default user path. Re-enable a PMTiles-only route only after `.pmtiles` files are present and the build path is reliable on the target environment.

**Build full PMTiles pipeline:**

```powershell
python scripts/init_storage.py
python scripts/check_registry.py
python scripts/build_web_map_data.py --cable-geometry-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv --allow-license-review --max-public-mb 5
python scripts/build_pmtiles_inputs.py
python scripts/build_atlas_core.py
python scripts/build_pmtiles.py --all --max-public-mb 25
python scripts/check_atlas_core.py
python scripts/check_pmtiles_outputs.py --max-public-mb 25
cd frontend
npm install
npm run build
cd ..
```

Then test locally:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173 and verify the default GeoJSON map first:
- Graticule is visible
- Power plants render as colored circles (if built)
- Submarine cables render as lines (if built)
- Data centers render as points (if built)
- Zoom/pan works smoothly without lag
- Click on any asset opens a popup with details
- Layer toggles work correctly
- Debug overlay shows map status

#### Build PMTiles Inputs

Generate GeoJSON/NDJSON feature files for tippecanoe:

```powershell
python scripts/build_pmtiles_inputs.py
```

or:

```powershell
make build-pmtiles-inputs
```

This script reads `atlas_web_data.json` and produces:
- `data/cache/pmtiles/power_plants.geojson` — point features with name, country, fuel, capacity
- `data/cache/pmtiles/submarine_cables.geojson` — line/multiline features with name, source, license
- `data/cache/pmtiles/data_centers.geojson` — point features with name, operator, country, city

All coordinates are validated to be within valid ranges (-180..180 lon, -90..90 lat).

#### Check PMTiles

Validate PMTiles files exist and are within size limits:

```powershell
python scripts/check_pmtiles_outputs.py --max-public-mb 25
```

or:

```powershell
make check-pmtiles
```

This checks:
- `frontend/public/tiles/power_plants.pmtiles` exists and is < 25 MB
- `frontend/public/tiles/submarine_cables.pmtiles` exists and is < 25 MB
- `frontend/public/tiles/data_centers.pmtiles` exists and is < 25 MB

If a file exceeds the size limit, it is moved to `data/tiles/` and marked for object storage (Cloudflare R2, S3, Vercel Blob, etc.).

#### Deploying large PMTiles

The Europe all-voltage `power_lines.pmtiles` file is about 190.37 MB. Do not deploy it as a normal Vercel frontend/static asset on Hobby-safe deploys. Upload it to object storage and point the atlas registry at the remote file instead.

Object storage requirements:
- Public HTTPS URL
- HTTP Range Requests
- CORS for the production frontend and local dev

Good storage options include Cloudflare R2, AWS S3 plus CloudFront, Vercel Blob public store, Azure Blob, and Google Cloud Storage.

Generic CORS guidance:

```json
{
  "AllowedOrigins": [
    "https://frontend-wheat-seven-24.vercel.app",
    "http://localhost:5173"
  ],
  "AllowedMethods": ["GET", "HEAD", "OPTIONS"],
  "AllowedHeaders": ["Range", "Origin", "Accept"],
  "ExposeHeaders": ["Accept-Ranges", "Content-Range", "Content-Length"]
}
```

Cloudflare R2 manual flow:

1. Create a public bucket.
2. Upload `data/tiles/power_lines.pmtiles`.
3. Configure CORS with the origins, methods, allowed headers, and exposed headers above.
4. Copy the public URL.
5. Set the local environment variable:

```powershell
$env:POWER_LINES_PMTILES_URL="https://<domain>/power_lines.pmtiles"
```

6. Rebuild the registry:

```powershell
python scripts/build_atlas_core.py
```

7. Run deploy preflight:

```powershell
python scripts/preflight_deploy.py --max-local-pmtiles-mb 100
```

When `POWER_LINES_PMTILES_URL` is set, `atlas_core.json` writes `tile_registry.power_lines.url` as `pmtiles://https://<domain>/power_lines.pmtiles`. Without it, large local power-line PMTiles remain blocked from deploy by design.

#### Deployment with PMTiles

After building small PMTiles or configuring remote large PMTiles:

```powershell
python scripts/preflight_deploy.py --max-local-pmtiles-mb 100
cd frontend
npm install
npm run build
cd ..
vercel.cmd --prod
```

Then test the production URL:

```
https://your-frontend-url.vercel.app/
```

Small PMTiles can be served from `frontend/public/tiles/` via the standard HTTP protocol. Large PMTiles should use remote object storage. The frontend's `pmtiles` protocol handler supports both `pmtiles:///tiles/example.pmtiles` and `pmtiles://https://<domain>/example.pmtiles`.

#### Troubleshooting PMTiles

**Black screen or missing PMTiles experiment layers:**
1. Check browser console for errors
2. Verify `atlas_core.json` exists: `python scripts/check_atlas_core.py`
3. Verify PMTiles files exist: `python scripts/check_pmtiles_outputs.py`
4. Check network tab for 404s on `.pmtiles` file requests

**Tippecanoe not found:**
- Install via WSL/Ubuntu: `sudo apt-get install tippecanoe`
- Or via Homebrew (macOS): `brew install tippecanoe`
- Or use Docker: `docker run --rm -v $(pwd):/work tippecanoe tippecanoe --version`

**Missing setup instructions dialog:**
- If all PMTiles files exist but one is missing from the UI, check `atlas_core.json` tile_registry status entries
- Ensure `python scripts/build_atlas_core.py` was run after building PMTiles

**Performance issues:**
- PMTiles zoom level range is 0-12 by default; tiles are built with `--drop-densest-as-needed`
- If render lag is severe, check browser DevTools Performance tab
- Verify GPU acceleration is enabled in browser settings
