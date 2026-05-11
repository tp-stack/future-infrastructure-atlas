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

1. **Read** a registered dataset from a local CSV file
2. **Create or require** a raw provenance manifest
3. **Validate** required CSV fields, latitude, and longitude
4. **Normalize** valid records into canonical asset-like JSONL with confidence metadata
5. **Write** processed output atomically to `data/processed/{dataset_key}/`
6. **Write** an ingestion manifest to `data/cache/`
7. **Optionally load** processed records into PostGIS if the database is available

Ingest the sample fixture:

```powershell
python scripts/ingest_dataset.py --dataset-key wri_global_power_plants --file-path tests/fixtures/sample_power_plants.csv
```

or:

```powershell
make ingest-fixture
```

Optionally load processed records to PostGIS:

```powershell
python scripts/load_processed_to_postgis.py --processed-path data/processed/wri_global_power_plants/<run_id>.jsonl
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
python scripts/build_web_map_data.py --max-public-mb 5
```

or:

```powershell
make build-map-data
```

This script:
1. Reads all three CSVs (streaming as needed)
2. Validates coordinates
3. Normalizes into compact frontend JSON
4. Writes to `frontend/public/data/atlas_web_data.json` if under 5 MB
5. Otherwise writes to `data/processed/web/atlas_web_data.json` and exits non-zero

**5 MB frontend payload limit:** If the generated JSON exceeds 5 MB, it is written to the Git-ignored `data/processed/web/` directory instead of `frontend/public/data/`. This prevents large data files from being committed to the repository.

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

The map uses:
- React + TypeScript + Vite
- MapLibre GL JS with dark atlas style
- Power plant points colored by fuel type (amber/orange theme)
- Data center points in white/silver
- Submarine cable lines in cyan/blue
- Layer toggles, fuel/country/capacity filters
- Click popups with asset details
- Stats panel (loaded counts, rejected records)
- Source attribution and disclaimer panel
- Museum-grade institutional dark theme

### Safety Warnings

- Never commit raw CSVs or large generated data files
- Always verify `git status` before committing
- The build script enforces a 5 MB limit on frontend data
- If the limit is exceeded, data goes to `data/processed/web/` (Git-ignored)
- Test before deploying: `python scripts/build_web_map_data.py --max-public-mb 5`

### Tests

```powershell
pytest -q tests/test_build_web_map_data.py
```
