# Learnings

## 2026-05-21 - Atlas Security Audit And Hardening

- **Issue fixed:** production site had no security headers, an inline script incompatible with CSP, a global MapLibre instance leak, and a raw PeeringDB CSV exposed as a static asset.
- **Root cause:** no `vercel.json` existed to configure security headers; inline script in `index.html` predated CSP requirements; `window.__atlasMap` was added for debugging without removal; `fetch_peeringdb_datacenters.py` wrote a public CSV that no frontend code consumed.
- **Solution:**
  - Created `frontend/vercel.json` with CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, and COOP headers.
  - Moved inline theme script to `frontend/public/theme-init.js` for CSP compatibility.
  - Removed `window.__atlasMap` global exposure from `AtlasMap.tsx`.
  - Removed `frontend/public/data/datacenters_public.csv` and blocked `*.csv`/`*.geojson` in public/data via `.gitignore`.
  - Wrote `SECURITY_AUDIT.md` with full findings and validation commands.
- **Validation:** `npm run build` passes; `npm audit` reports 0 vulnerabilities; `pytest -q` passes; `python -m atlas.storage .` passes; `python scripts/check_frontend_data.py` passes; `python scripts/check_registry.py` passes (15 pre-existing warnings, 0 errors).
- **Deployment:** verified at https://frontend-wheat-seven-24.vercel.app/
- **Remaining risks:** debug routes publicly accessible (accepted for support), no pip-audit/bandit in CI, no SRI hashes.

## 2026-05-19 - Cable Geometry Coverage Preserved In Web Bundle

- Issue fixed: regenerated public data was falling back to a tiny legacy cable geometry set instead of the reviewed KMCD-derived geometry CSV.
- Root cause: SCN cable segment rows were not collapsed into cable systems, and KMCD geometry-only cable records were not appended when they had no matching SCN inventory row.
- Solution: merged duplicate cable segment rows, merged duplicate geometry rows into MultiLineString features, and appended geometry-only public cable records while keeping `source_license: to_verify` and `license_review_required: true`.
- Validation: `python scripts/build_web_map_data.py --cable-geometry-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv --allow-license-review --max-public-mb 5`; `python scripts/check_frontend_data.py`; `pytest -q --ignore=tests/test_visual_regression.py`.
- Remaining risk: KMCD/underlying cable geometry license still requires review before production/commercial use.

## 2026-05-19 - Visual Regression Guard For Core Map Routes

- Issue fixed: black/empty map regressions could pass CI because no automated test inspected rendered pixels.
- Root cause: existing tests validated data and builds, but not whether user-facing routes actually paint infrastructure layers.
- Solution: added a standard-library visual regression script that starts Vite, captures headless Chrome screenshots for `/`, `?reliableMap=1`, and `?maplibreMap=1`, decodes PNG pixels, crops the map area, and fails on low visual signal. CI now runs this guard after frontend build. `?maplibreMap=1` is now a protected reliable-renderer alias; `?zoomMap=1` remains the raw MapLibre diagnostic route.
- Validation: `python scripts/check_visual_regression.py`; `pytest tests/test_visual_regression.py -q`; `python -m atlas.storage .`; `cd frontend && npm.cmd run build`; `pytest -q --ignore=tests/test_visual_regression.py` (`278 passed, 5 skipped`).
- Deployment: https://frontend-wheat-seven-24.vercel.app/
- Remaining risk: CI runners must have Chrome/Chromium and frontend npm dependencies installed; the script fails clearly if either is missing.
- Next recommended issue: add a second screenshot profile for mobile/narrow viewports so sidebar and map-stage regressions are caught too.

## 2026-05-19 - Added Reliable Canvas Map Baseline

- Issue fixed: the primary view needed a renderer that stays usable even when MapLibre/WebGL or external globe packages fail.
- Root cause: globe repositories under the GitHub topic are either decorative WebGL components, Three.js data-globe libraries, or heavier GIS engines; they still depend on WebGL and would not remove the current critical rendering risk.
- Solution: added a self-contained React canvas renderer as the normal app default and exposed <code>?reliableMap=1</code>; MapLibre remains available through <code>?maplibreMap=1</code> and <code>?zoomMap=1</code>.
- Validation: `python scripts/init_storage.py`; `python scripts/check_registry.py`; `python scripts/build_web_map_data.py --max-public-mb 5`; `python scripts/check_frontend_data.py`; `python -m atlas.storage .`; `python scripts/check_pmtiles_outputs.py --max-public-mb 25`; `python scripts/build_atlas_core.py`; `python scripts/check_atlas_core.py`; `pytest -q`; `cd frontend && npm.cmd run build`; local Chrome/CDP route sweep for `/`, `?reliableMap=1`, `?reliableMap=1&proof=1`, `?maplibreMap=1`, and `?zoomMap=1`.
- Deployment: https://frontend-wheat-seven-24.vercel.app/
- Remaining risk: the reliable renderer is intentionally simple and does not replace PMTiles/object-storage architecture for large production layers.
- Next recommended issue: add automated visual regression checks for <code>/</code>, <code>?reliableMap=1</code>, and <code>?maplibreMap=1</code>.

## 2026-05-19 - PMTiles Artifact Build Kept Storage-Safe

- Issue fixed: PMTiles could be generated, but public `.pmtiles` files violated repository storage safety.
- Root cause: `frontend/public/tiles/*.pmtiles` is not an allowed repository location; storage checks block `.pmtiles` outside ignored data directories even when files are below the public-size cap.
- Solution: added Docker fallback for Tippecanoe, generated PMTiles as ignored artifacts under `data/tiles/`, updated `atlas_core.json` to mark them `artifact_only`, and updated PMTiles checks/observatory output to distinguish artifact availability from public serving.
- Validation: `python scripts/build_pmtiles.py --layer submarine_cables --max-public-mb 25`; `python scripts/build_atlas_core.py`; `python scripts/check_atlas_core.py`; `python scripts/check_pmtiles_outputs.py --max-public-mb 25`; `python -m atlas.storage .`; `pytest -q`; `cd frontend && npm.cmd run build`.
- Deployment: pending; PMTiles artifacts are local and ignored until hosted through object storage or copied into a deployment artifact outside git.
- Remaining risk: `?pmtilesMap=1` still shows the setup warning in deployed builds because the generated PMTiles are not publicly served.
- Next recommended issue: add an object-storage or deployment-artifact path for `/tiles/*.pmtiles`, then verify `?pmtilesMap=1` renders tiled infrastructure.

## 2026-05-14 - Stabilized Clean MapLibre Renderer

- Issue fixed: the normal app and `?zoomMap=1` needed a reliable, independent MapLibre path that visibly renders power plants, data centers, submarine cables, popups, and reset/fit controls.
- Root cause: the clean zoom route was missing and the normal route depended on the older `AtlasMap` path, where power plant clustered sources could fail to render even while other layers loaded.
- Solution: added `ZoomableAtlasMap.tsx`, expanded shared GeoJSON helpers, routed the normal app and `?zoomMap=1` through the clean renderer, kept `AtlasMap` as the diagnostics/canvas fallback, and added a static build observatory.
- Validation: `python scripts/init_storage.py`; `python scripts/check_registry.py`; `python scripts/build_web_map_data.py --max-public-mb 5`; `python scripts/check_frontend_data.py`; `pytest -q`; `python -m atlas.storage .`; `python scripts/build_pmtiles_inputs.py`; `python scripts/build_atlas_core.py`; `python scripts/check_atlas_core.py`; `python scripts/check_pmtiles_outputs.py --max-public-mb 25`; `python scripts/build_observatory.py --live-url https://frontend-wheat-seven-24.vercel.app/`; `cd frontend && npm.cmd install && npm.cmd run build`; local and production CDP route sweeps; cluster-click and data-center popup/details checks.
- Deployment: https://frontend-wheat-seven-24.vercel.app/
- Remaining risk: PMTiles binaries are still absent because Tippecanoe is not installed on this Windows environment; the PMTiles route shows the setup warning instead of tiled infrastructure.
- Next recommended issue: install Tippecanoe in WSL/Linux and build/check PMTiles outputs for the three primary layers.

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
