# Architecture

FUTURE Infrastructure Atlas is planned as a staged geospatial data platform:

1. Source registry and ingestion manifests
2. Raw data acquisition into local or object storage
3. Reproducible staging and processing pipelines
4. Database loading and spatial indexing
5. Vector tile generation
6. API and frontend rendering

Step 1 establishes only the repository skeleton and safety guardrails.

## Repository Boundary

The repository stores source code, configuration, documentation, schema files, migrations, tiny test fixtures, and metadata manifests. It does not store large raw datasets, processed extracts, tile packages, local databases, cache files, generated reports, or logs.

## Data Boundary

The `data/` directory is a local working area. Its subdirectories are ignored by Git except for `.gitkeep` files and `data/README.md`. Future deployments should move raw and processed objects to managed object storage while keeping metadata manifests in Git.

## Safety Boundary

`atlas.storage.validate_repo_file_safety` checks for unsafe files before commit or CI. It flags large files outside approved data directories and blocks common geospatial, raster, tile, and local database extensions outside approved local storage.
