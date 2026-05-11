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
