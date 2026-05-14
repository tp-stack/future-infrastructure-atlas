# Learnings

## 2026-05-14 - Reliable MapLibre Route And Global Fit

- Issue fixed: `?zoomMap=1` and `?pmtilesMap=1` were not reliable standalone map routes, and MapLibre could open at a pathological street-scale view instead of the global infrastructure view.
- Root cause: `App.tsx` only routed the debug map, while global bounds could resolve to an exact 360-degree longitude span with `renderWorldCopies: false`, which MapLibre handled poorly and surfaced as empty/black map states.
- Solution: added explicit MapLibre and PMTiles routes, guarded PMTiles interactions when tile layers are missing, and clamped global fit bounds to an inset world extent shared by viewport helpers and MapLibre max bounds.
- Validation: `python scripts/init_storage.py`; `python scripts/check_registry.py`; `python scripts/build_web_map_data.py --max-public-mb 5`; `python scripts/check_frontend_data.py`; `python scripts/build_atlas_core.py`; `python scripts/check_atlas_core.py`; `python scripts/check_pmtiles_outputs.py --max-public-mb 25`; `pytest -q`; `python -m atlas.storage .`; `cd frontend && npm.cmd install && npm.cmd run build`; local Chrome route sweep for `/`, `?zoomMap=1`, `?debugMap=1`, `?debugMap=1&proof=1`, and `?pmtilesMap=1`.
- Deployment: https://frontend-wheat-seven-24.vercel.app/
- Remaining risk: PMTiles files are still absent by design; `?pmtilesMap=1` now fails gracefully but does not render tiled infrastructure until PMTiles are generated.

## 2026-05-14 - Ingestion Fixture Validation Baseline

- Issue fixed: `run_fixture_ingestion` fixture tests failed on canonical output fields and Windows path assertions.
- Root cause: the fixture wrapper returned legacy `run_ingestion` JSONL records while newer fixture tests expected canonical layer records; tests also checked POSIX path substrings.
- Solution: convert fixture-wrapper JSONL output to canonical asset fields and make path assertions platform-neutral.
- Validation: `python scripts/init_storage.py`; `python scripts/check_registry.py`; `python scripts/build_web_map_data.py --max-public-mb 5`; `python scripts/check_frontend_data.py`; `pytest -q`; `python -m atlas.storage .`; `cd frontend && npm.cmd install && npm.cmd run build`.
- Deployment: skipped; this was a backend/test baseline fix, not a frontend rendering change.
- Remaining risk: `atlas_core.json` can still drift from regenerated `atlas_web_data.json` cable counts.

## 2026-05-14 - Dirty Tree Cleanup

- Issue fixed: repository had validated-but-uncommitted Atlas frontend, PMTiles helper, and generated public metadata changes.
- Root cause: previous work left staged and unstaged changes, and `atlas_core.json` had stale cable counts relative to regenerated `atlas_web_data.json`.
- Solution: rebuilt `atlas_web_data.json`, regenerated `atlas_core.json`, validated the full suite, and committed the safe source/public-data changes.
- Validation: `python scripts/check_frontend_data.py`; `python scripts/check_atlas_core.py`; `python scripts/check_pmtiles_outputs.py`; `pytest -q`; `python -m atlas.storage .`; `cd frontend && npm.cmd install && npm.cmd run build`.
- Deployment: skipped; cleanup was not a visual rendering fix.
- Remaining risk: PMTiles files are still missing by design until generated separately.
