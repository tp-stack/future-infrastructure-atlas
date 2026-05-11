# Data Policy

Large data files must never be committed to Git. This repository is for code, configuration, documentation, schemas, tiny test fixtures, and metadata manifests only.

## Storage Rules

- Raw, staging, processed, tile, cache, report, and log files belong under `data/` locally or in future object storage.
- Raw data is immutable. If a source changes, store a new version instead of modifying an existing raw asset.
- Processed data must be reproducible from raw inputs, source metadata, transformation code, and configuration.
- Generated outputs such as GeoJSON, GeoPackage, shapefiles, rasters, Parquet files, DuckDB databases, PMTiles, and MBTiles are ignored by Git.

## Dataset Metadata

Every dataset must have:

- source name and source ID
- license and allowed usage
- retrieval timestamp
- source URL or acquisition path
- checksum using the configured algorithm
- processing version when derived from another dataset

## Confidence and Sensitivity

Every geospatial asset must carry a confidence score. The score should reflect source reliability, spatial precision, recency, and processing quality.

Sensitive infrastructure must be generalized before publication. Exact operational details should not be exposed when they could create security risk.

## Prohibited Data

- No classified data.
- No unlawfully obtained data.
- No operational vulnerability mapping.
- No instructions, annotations, or derived products intended to enable disruption of infrastructure.
- No exact sensitive facility mapping when a generalized regional representation is sufficient.
