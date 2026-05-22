# Global Infrastructure Atlas — Agent Reference

## Project Overview

Interactive web map of global energy, internet, and compute infrastructure. Displays ~50K+ power plants, submarine cables, and data centers with clustering, filtering, and selection. Built with **React 18 + TypeScript + Vite 6** (frontend) and a **Python data pipeline** (backend).

**Stack:**
- `maplibre-gl` v4.7.1 — primary map renderer (WebGL vector/raster tiles)
- `pmtiles` v4.4.1 — local vector tile protocol for offline-capable tile serving
- React 18 — UI components and state management
- Vite 6 — dev server and bundler
- Python 3.11+ — data processing scripts

---

## Repository Layout

```
future-infrastructure-atlas/
  frontend/                    # React + Vite SPA
    src/
      main.tsx                 # Entry point, renders <App>
      App.tsx                  # Root: data loading, routing, sidebar layout
      styles.css               # All CSS (~1167 lines)
      map/
        AtlasMap.tsx           # DEFAULT — MapLibre + ArcGIS World Topo basemap
        ReliableAtlasMap.tsx   # Canvas-only equirectangular fallback (?reliableMap=1)
        ZoomableAtlasMap.tsx   # Dark MapLibre (?zoomMap=1 or ?maplibreMap=1)
        SimpleAtlasMap.tsx     # Debug MapLibre (?debugMap=1)
        PMTilesAtlasMap.tsx    # PMTiles vector tile viewer (?pmtilesMap=1)
        InfrastructureCanvasOverlay.tsx  # Canvas overlay drawn on top of MapLibre
        basemaps.ts            # ArcGIS World Topo raster tile source/layer/style
        layers.ts              # Color constants, paint properties for all layers
        types.ts               # TypeScript interfaces (PowerPlant, Cable, DataCenter, etc.)
        geojson.ts             # Build GeoJSON FeatureCollections from AtlasData
        viewport.ts            # Bounds computation, zoom helpers, isZoomPathological
        interaction.ts         # Screen-space hit-testing (buildPickIndex, findNearest)
        pmtiles.ts             # PMTiles protocol registration, source/layer factory functions
      components/
        LayerPanel.tsx         # Layer toggles + dropdown filters (fuel, country, min MW)
        Legend.tsx             # Color legend for fuel types
        StatsPanel.tsx         # Counts per layer
        UnmappedPanel.tsx      # Shows unmapped infrastructure records
        SourcePanel.tsx        # Data source attributions + disclaimer
        AssetDetailsPanel.tsx  # Detail overlay when asset is clicked
        AssetPopup.tsx         # Popup component for MapLibre popups
        ErrorBoundary.tsx      # React error boundary
  scripts/                     # Python data pipeline
    build_web_map_data.py      # Main: produces frontend/public/data/atlas_web_data.json
    build_atlas_core.py        # Produces frontend/public/data/atlas_core.json (metadata + PMTiles registry)
    build_pmtiles.py           # Converts GeoJSON → .pmtiles tiles
    build_pmtiles_inputs.py    # Prepares NDGeoJSON inputs for tippecanoe
    ingest_dataset.py          # Ingests raw CSVs/GeoJSON into PostGIS
    init_db.py                 # Creates PostGIS schema and tables
    fetch_peeringdb_datacenters.py       # Fetches PeeringDB facility data
    fetch_peeringdb_datacenters_coordinates.py  # Geocodes PeeringDB entries
    fetch_and_build_cable_geometry_csv.py      # Fetches submarine cable geometries
    check_*.py                 # Validation/regression scripts
    load_processed_to_postgis.py  # Loads processed data into PostGIS
    init_storage.py            # Sets up storage buckets
    clean_cache.py             # Cleans temporary cached data
  data/                        # Data directory (gitignored for raw/processed/tiles/cache)
  pyproject.toml               # Python deps (psycopg, PyYAML, pytest)
```

---

## Data Flow

### Frontend Data Loading (App.tsx)
1. On mount, fetches `/data/atlas_core.json` (optional metadata/tile registry)
2. Then fetches `/data/atlas_web_data.json` (required — the main dataset)
3. `AtlasData` contains: `metadata`, `power_plants[]`, `cables[]`, `data_centers[]`
4. Data is passed via props to map components
5. Map components build GeoJSON FeatureCollections from the data using `geojson.ts`

### Python Data Pipeline
```
Raw sources (CSV/GeoJSON/KMZ) → ingest_dataset.py → PostGIS
  → build_web_map_data.py → atlas_web_data.json (for frontend)
  → build_atlas_core.py → atlas_core.json (metadata for frontend)
  → build_pmtiles_inputs.py → NDGeoJSON → tippecanoe → .pmtiles files
```

---

## URL Parameters (Route Matrix)

| Param | Component | Description |
|-------|-----------|-------------|
| *(none)* | `AtlasMap` | **Default.** MapLibre + ArcGIS World Topo basemap + sidebar UI. GeoJSON sources, debounced updates. |
| `?reliableMap=1` | `ReliableAtlasMap` | Full-screen canvas-only equirectangular map (no basemap tiles) |
| `?maplibreMap=1` | `ReliableAtlasMap` | Alias for reliableMap (same full-screen canvas map) |
| `?zoomMap=1` | `ZoomableAtlasMap` | Dark minimal MapLibre, no basemap tiles, full-screen |
| `?debugMap=1` | `SimpleAtlasMap` | Debug MapLibre with light topo + debug overlay |
| `?pmtilesMap=1` | `PMTilesAtlasMap` | PMTiles vector tile viewer with toggles |
| `?canvasFallback=1` | — | Enables `InfrastructureCanvasOverlay` on `AtlasMap` |
| `?proof=1` | Various | Shows proof/test points on some map renderers |

**Key fact:** Default route renders `AtlasMap` (MapLibre with basemap). Previous default was `ReliableAtlasMap` (canvas-only) — changed in App.tsx to use AtlasMap.

---

## Map Renderers — Detailed Comparison

### 1. AtlasMap.tsx (Default, ~543 lines)
- **Renderer:** MapLibre GL JS
- **Basemap:** ArcGIS World Topo (raster tiles from `services.arcgisonline.com`)
- **Sources:** 3 GeoJSON sources: power-plants (clustered), data-centers, submarine-cables
- **Layers:** submarine-cable-lines, power-clusters, power-cluster-count, power-points, data-center-points
- **Controls:** NavigationControl (top-right), ScaleControl (bottom-left)
- **Interactions:** click → asset selection, mousemove → hover cursor, cluster expansion on click
- **Fitting:** `fitToData()` with `maxZoom: 2.5`, padded bounds
- **Overlay:** `InfrastructureCanvasOverlay` optionally drawn on top (when `canvasEnabled` is true)
- **Key logic:**
  - `clusterMaxZoom: 7` — clustering stops at zoom 7
  - `addPowerPlantLayers()` — adds clustered power plant circles, counts, and individual points
  - `handleCanvasDiagnostics` — reset to global view if 0 points drawn and zoom is pathological (>8)
  - Fuel color match expression auto-generated from `FUEL_COLORS` via `fuelMatch.ts`
  - Filter updates debounced at 300ms via `useDebounce`
  - CanvasOverlay conditionally rendered (only when `canvasEnabled` is true)
  - All timer cleanup on unmount via `cleanupFnsRef`
  - **No more 4s setTimeout rebuild hack** — removed in MVP Phase 1.1

### 2. ReliableAtlasMap.tsx (~592 lines)
- **Renderer:** Pure HTML Canvas 2D
- **Projection:** Equirectangular (flat)
- **Basemap:** Dark solid background + world outline
- **Controls:** Custom pan (pointer drag), zoom (wheel), double-click zoom-in
- **Clustering:** Manual cell-based clustering (cellSize = 36 at zoom < 2, 26 at zoom 2-5, 0 at zoom >= 5)
- **Performance:** Draws all features every frame — can be slow with 50K+ points at high zoom
- **Zoom limits:** 0.75 – 28 (clampView)
- **Popup:** Absolute-positioned HTML div, computed on click
- **Best for:** Reliability when WebGL fails, debugging projection issues

### 3. ZoomableAtlasMap.tsx (~479 lines)
- **Renderer:** MapLibre GL JS
- **Basemap:** Dark solid background (`#05070a`), no basemap tiles
- **Sources:** 4 GeoJSON: graticule, power-plants (clustered), data-centers, submarine-cables
- **Style:** Minimal inline style (no external tile server needed)
- **Used via:** `?zoomMap=1` or `?maplibreMap=1`

### 4. SimpleAtlasMap.tsx (~294 lines)
- **Renderer:** MapLibre GL JS
- **Basemap:** ArcGIS World Topo (same as AtlasMap)
- **Purpose:** Debug / quick verification
- **Overlay:** Top-left debug panel showing counts, zoom, center

### 5. PMTilesAtlasMap.tsx (~329 lines)
- **Renderer:** MapLibre GL JS + PMTiles protocol
- **Data source:** Local `.pmtiles` vector tile files
- **Protocol:** `registerPMTilesProtocol()` from `pmtiles.ts`
- **Used via:** `?pmtilesMap=1`
- **Requires:** `atlas_core.json` with `tile_registry` entries

---

## Canvas Overlay System (InfrastructureCanvasOverlay.tsx)

An HTML Canvas drawn on top of the MapLibre `<div>` (z-index 2, pointer-events: none). Enabled via `canvasEnabled` prop or `?canvasFallback=1`.

**Behavior:**
- If `mapInstance` is available → uses MapLibre's `map.project()` for Mercator projection
- If no map instance → falls back to equirectangular projection
- Draws: power plants (colored circles), cables (lines), data centers (teal circles), graticule, test points
- Reports diagnostics via `CanvasDiagnostics` callback (used for "0 points" warnings)
- Updated via `requestAnimationFrame` + `ResizeObserver`

**Diagnostics emitted:**
- `canvasWidth/Height`, `powerPlantsDrawn`, `cableLinesDrawn`, `dataCentersDrawn`
- `recordsReceived`, `validCoords`, `currentZoom`, `projectionMode`, `lastError`

---

## Key Component Details

### App.tsx (~545 lines)
- **Data loading:** Two fetches on mount (`atlas_core.json` optional, `atlas_web_data.json` required)
- **State management:** `useState` for data, filters, visibleLayers, sidebar, diagnostics
- **URL routing:** Early returns for special map routes, default renders AtlasMap
- **Sidebar:** CSS grid layout with 360px sidebar + map area
- **Conditional rendering:** Coverage warnings, "zero points" warnings, filter badge
- **Map rendering (line 299):** `reliableMap ? ReliableAtlasMap : AtlasMap` (default)

### LayerPanel.tsx
- 3 layer toggles: Power Plants, Submarine Cables, PeeringDB facilities
- 3 filter controls: Fuel Type dropdown, Country dropdown, Min Capacity number input
- Shows mapped/total counts per layer with status chip (mapped/partial/unmapped)

### AssetDetailsPanel.tsx
- Renders when asset is selected (clicked on map)
- Duck-types the asset: `"f" in asset` → power_plant, `"op" in asset` → data_center
- Shows type-specific fields with coordinate precision warnings

### viewport.ts
- `isZoomPathological(zoom)` → true when `zoom > 8`
- `FIT_WORLD_MIN_LON` = -179.5, `FIT_WORLD_MAX_LON` = 179.5
- `expandBounds()` pads by degree, clamped to world bounds
- `getDefaultGlobalBounds()` → `[-179.5, -60]` to `[179.5, 85]`

### interaction.ts (screen-space hit-testing)
- `buildPickIndex()` — pre-projects all assets to screen coords
- `findNearest()` — Euclidian distance scan with maxDistPx (default 12)
- Separate handling for power plants (radius 8), data centers (radius 14), cables (radius 6)

---

## CSS Architecture (styles.css, ~1167 lines)

| Section | Lines | Description |
|---------|-------|-------------|
| Reset | 1-14 | box-sizing, full viewport, dark theme |
| App shell | 16-39 | CSS grid, sidebar collapse, map-only mode |
| Loading/Error | 41-115 | Spinner, error state with file-missing hint |
| Side panel | 117-204 | 360px dark panel, backdrop blur, toggle |
| Filters | 300-340 | Dropdowns, number input, filter summary |
| Map area | 446-562 | Flex layout, full-height, overlay controls |
| Popups | 564-637 | MapLibre popup overrides, dark theme |
| Reliable/Zoomable routes | 638-855 | Canvas/MapLibre full-screen variants |
| Top bar | 857-914 | Stats bar, filter badge, warning badge |
| Diagnostics | 916-947 | Floating panel with renderer metrics |
| Asset details | 987-1092 | Modal overlay, centered panel |
| Responsive | 1130-1167 | Mobile: fixed sidebar, hidden title |

---

## Common Issues & Fixes

### Map not visible / blank
- **Default was ReliableAtlasMap** (canvas-only, no basemap). Now fixed to default AtlasMap (MapLibre with basemap).
- Check that `atlas_web_data.json` exists in `frontend/public/data/`
- Check browser console for fetch errors (404 on data file)
- Check for `mapStatus.error` rendering in AtlasMap

### Map breaks when zoomed in
- **ReliableAtlasMap:** Canvas equirectangular projection loses precision at high zoom. All points redrawn every frame — performance degrades with 50K+ points.
- **Fix:** Use AtlasMap (MapLibre) which handles zoom properly with tile-based rendering.
- For canvas overlay: `isZoomPathological(zoom > 8)` triggers auto-reset to global view.

### Cluster rendering issues
- AtlasMap has a 4-second timeout (line 232) that removes and re-adds power plant layers.
- This is a workaround for MapLibre cluster source update issues.
- `clusterMaxZoom: 7` — beyond this, individual points render.

### 0 points drawn warning
- Triggered when `powerPlantsDrawn === 0 && recordsReceived > 1000`
- Often means camera is outside data bounds. Click "Reset Global View" button.
- `handleCanvasDiagnostics` in AtlasMap auto-resets to global view in this case (unless user has interacted).

### Canvas overlay not showing
- Must have `canvasEnabled={true}` prop on AtlasMap (controlled via diagnostics toggle or `?canvasFallback=1`)
- Overlay is **conditionally rendered** — when disabled, no `<canvas>` element exists, no `requestAnimationFrame` runs
- Overlay uses `pointer-events: none` — it's visual only, interaction goes through MapLibre

### Font/Text missing in MapLibre
- MapLibre layers using `text-font` require glyphs from `MAPLIBRE_GLYPHS_URL` (`demotiles.maplibre.org`)
- `power-cluster-count` layer uses `["Open Sans Bold", "Arial Unicode MS Bold"]`
- If glyphs are unreachable, cluster count labels won't render (but map otherwise works)

---

## Development Commands

```bash
cd frontend
npm run dev          # Vite dev server (hot reload)
npm run build        # tsc -b && vite build (production build)
npm run preview      # Vite preview of production build
```

**Important:** Always run `npm run build` (or at least `npx tsc --noEmit`) after making changes. TypeScript strict mode is enabled.

## New Files (MVP Phase 1)

| File | Purpose |
|------|---------|
| `frontend/src/map/coords.ts` | Shared `getLon`/`getLat`/`isValidLonLat`/`validPointFromRecord`/`toValidPoint` utilities |
| `frontend/src/map/fuelMatch.ts` | `buildFuelCircleColorExpression()` — dynamically builds MapLibre match expression from `FUEL_COLORS` |
| `frontend/src/utils/debounce.ts` | `useDebounce` hook — generic debounce with cleanup |
| `frontend/src/utils/cache.ts` | `cachedFetch` — IndexedDB-backed fetch with configurable TTL |

## Recent Changes (MVP Phase 1)

| Change | Detail |
|--------|--------|
| Cluster rebuild hack removed | 4-second setTimeout tear-down/re-add cycle eliminated. Source updates use debounce instead. |
| Filter debouncing | `doUpdateSources` debounced at 300ms — stops cascading GeoJSON re-parses |
| Conditional CanvasOverlay | `<canvas>` element only rendered when `canvasEnabled={true}` — no unnecessary `requestAnimationFrame` |
| Timeout cleanup | All timers tracked via `cleanupFnsRef`, cleared on unmount |
| IndexedDB caching | `cachedFetch` stores JSON in IndexedDB with 5-minute TTL, skips network on repeat visits |
| Asset search | Text input in LayerPanel searches power plants (name/country), cables (name), data centers (name/city) |
| Type discriminant | `kind: "power_plant"` / `"submarine_cable"` / `"data_center"` on all Asset types — replaces duck typing |
| Shared coords | `geojson.ts` and `InfrastructureCanvasOverlay.tsx` import from `coords.ts` instead of duplicating |
| Auto fuel colors | `buildFuelCircleColorExpression()` generates match expression from `FUEL_COLORS` — no hardcoded fuel list |

---

## Global Architecture Notes

The atlas now has two parallel delivery paths:

| Path | Files | Purpose |
|------|-------|---------|
| Metadata/core | `frontend/public/data/atlas_core.json` | Small registry with counts, source/license notes, and PMTiles URLs/status. No coordinate arrays. |
| Interactive GeoJSON fallback | `atlas_web_data.json`, `power_lines.json`, `substations.json` | Default route can render layers directly when PMTiles are missing or while optional data arrives late. |
| PMTiles vector tiles | `frontend/public/tiles/*.pmtiles` | Heavy render path for `power_plants`, `submarine_cables`, `data_centers`, `power_lines`, and `substations`. |
| Artifact storage | `data/tiles/*.pmtiles` | Build artifacts before deciding whether to expose tiles publicly or move them to object storage. |

Power-grid layers use OSM-compatible electricity schemas:
- `scripts/fetch_osm_global_power_grid.py` ingests fresh Geofabrik PBF extracts by region into ignored NDJSON, then writes metadata-only `power_lines.json` and `substations.json` with `pmtiles_input` references.
- `scripts/fetch_osm_europe_power_lines.py` preserves the existing Europe all-voltage OSM ArcGIS-derived pipeline for the first global pass.
- `scripts/fetch_openinframap_power_extract.py` reproduces an OpenInfraMap viewport by querying underlying OSM power data through Overpass. It must not scrape OpenInfraMap tiles; generated JSON/NDJSON stays under ignored `data/cache/`.
- `scripts/fetch_power_lines.py` and `scripts/fetch_pypsa_usa_power_grid.py` remain available for PyPSA-style CSV imports, but the global expansion path is Geofabrik OSM.
- `scripts/build_pmtiles.py --layer power_lines`, `--layer substations`, `--layer openinframap_power_lines`, and `--layer openinframap_substations` read either direct GeoJSON fallback features or metadata `pmtiles_input` NDJSON and build the corresponding `.pmtiles`.

Frontend layer factories live in `frontend/src/map/pmtiles.ts`. Keep PMTiles layer ids aligned with `AtlasMap.tsx` interaction ids:
- `power_lines_tiles-layer`
- `power_lines_cables_tiles-layer`
- `openinframap_power_lines_tiles-layer`
- `openinframap_power_cables_tiles-layer`
- `substations_tiles-layer`
- `openinframap_substations_tiles-layer`
- GeoJSON fallback ids: `power-line-lines`, `substation-points`

---

## Data Integrity Rules (Safety Invariants)

These are hard rules that must never be violated:
1. **No downloading new datasets** unless explicitly instructed
2. **No invented coordinates** — never infer submarine cable routes or geocode data centers
3. **No silent geocoding** — data center coordinates must come from authoritative sources
4. **No committing raw data** — `data/raw/`, `data/cache/`, `data/processed/`, `data/tiles/`, `data/logs/`, `data/reports/` are all gitignored
5. **Keep `frontend/tsconfig.tsbuildinfo` untracked**
6. **Preserve all source/license provenance** — warnings and attribution must be maintained
7. **PeeringDB facilities** must be labeled as public facilities/interconnection data, not as "every data center in the world"
