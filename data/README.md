# Local Data Directory

This directory is for local-only data. Do not commit raw datasets, processed outputs, tiles, caches, reports, logs, local databases, rasters, shapefiles, GeoPackages, Parquet files, PMTiles, or MBTiles.

Only this README and `.gitkeep` placeholders should be tracked here.

Use:

```powershell
python scripts/init_storage.py
```

to recreate the required local directories.
