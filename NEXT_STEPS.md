# Next Steps — Implementation Plan

## Current State

**MVP stability achieved.** The app now:
- Defaults to MapLibre with ArcGIS basemap (no longer canvas-only)
- Has proper debounced filter updates (no more 4s timeout hack)
- Conditionally renders canvas overlay (no wasted GPU cycles)
- Caches data in IndexedDB (skip network on repeat visits)
- Has asset search in sidebar
- Uses proper `kind` discriminant instead of duck typing
- Has shared coordinate utilities
- Auto-generates fuel color expressions from config
- Builds clean with zero TypeScript errors

**PMTiles data exists** at `data/tiles/power_plants.pmtiles`, `submarine_cables.pmtiles`, `data_centers.pmtiles` and `frontend/public/data/atlas_core.json`. But PMTiles aren't wired as default — they need to be copied to `frontend/public/tiles/` first.

---

## Phase 5 — PMTiles Default (High Impact)

### 5.1 Copy PMTiles to frontend public directory
```
cp data/tiles/*.pmtiles frontend/public/tiles/
```
- PMTiles are served as static files from `/tiles/`
- Add to `scripts/` as `deploy_tiles.sh` or a build step
- Update `.gitignore` if needed

### 5.2 Rewrite AtlasMap to auto-detect PMTiles
- On mount, try to fetch `atlas_core.json` tile registry
- If present → register PMTiles protocol, add vector tile sources + basemap
- If absent → fall back to current GeoJSON clustering
- This replaces the `?pmtilesMap=1` route with seamless auto-detection

**Why:** GeoJSON with 50K features blocks the main thread on filter changes. PMTiles serve vector tiles — only visible tiles are parsed, zoom levels are instant, clustering is built into the tile format.

### 5.3 Update `pmtiles.ts` to use `buildFuelCircleColorExpression`
- Line 58 has a hardcoded match expression missing half the fuel types
- Replace with shared utility from `fuelMatch.ts`

### 5.4 Consolidate map routes
- Remove `SimpleAtlasMap` and `ZoomableAtlasMap` as separate files
- Make the PMTiles+GeoJSON hybrid the one true default
- Keep `ReliableAtlasMap` as emergency WebGL fallback (`?reliableMap=1`)

---

## Phase 6 — Search-to-Map Navigation (High UX)

### 6.1 Click search result → fly to asset
- App.tsx needs `flyToAsset(lat, lon)` callback
- Search results in LayerPanel pass coordinates back to App
- Map flies to the asset and opens its popup
- Requires: coordinates in search results, callback plumbing

### 6.2 Search result debounce
- Currently fires on every keystroke
- Add 200ms debounce to search input (use existing `useDebounce` utility)

### 6.3 Clear search button
- Add an "x" button in the search input to clear the query

---

## Phase 7 — Testing (Medium Impact)

### 7.1 Vitest setup
```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```
- Add `vitest.config.ts`
- Add test script to `package.json`

### 7.2 Unit tests for utilities
- `coords.ts` — test `getLon`, `getLat`, `isValidLonLat`, `validPointFromRecord`
- `fuelMatch.ts` — test `buildFuelCircleColorExpression` output structure
- `geojson.ts` — test `buildPowerPlantGeoJSON` with filters
- `viewport.ts` — test bound computations
- `debounce.ts` — test timing

### 7.3 Component tests
- `LayerPanel` — test filter interactions
- `Legend` — test fuel colors render
- `ErrorBoundary` — test error catch

### 7.4 Visual regression
- The existing `scripts/check_visual_regression.py` captures screenshots
- Automate it in CI to compare map renders before/after changes

---

## Phase 8 — Data Pipeline Automation (Medium Impact)

### 8.1 Makefile or npm scripts
- `npm run data:pull` — fetch latest raw sources
- `npm run data:build` — run all Python build scripts
- `npm run data:validate` — run check scripts
- `npm run data:deploy` — copy tiles to frontend/public

### 8.2 Inline the data version
- Show dataset generation timestamp in the UI (currently shown in panel footer)
- Add a "Data updated" indicator in the top bar

### 8.3 Dataset diff viewer
- When data is rebuilt, show what changed (new power plants, removed cables, etc.)

---

## Phase 9 — Bundle & Performance (Medium Impact)

### 9.1 Code-split MapLibre
- `maplibre-gl` is 1MB+ in the bundle
- Dynamic import the map renderer: `const AtlasMap = lazy(() => import("./map/AtlasMap"))`
- Show loading skeleton while map loads
- Separate `ReliableAtlasMap` into its own chunk (only loaded on `?reliableMap=1`)

### 9.2 Lazy-load sidebar panels
- `StatsPanel`, `UnmappedPanel`, `SourcePanel` are always rendered
- Wrap each in `lazy()` + `<Suspense>`
- Shaves ~50KB from initial bundle

### 9.3 Remove inline SVGs
- Extract all inline SVG icons into a shared `icons.tsx` component
- Reduces CSS/HTML size, enables consistent styling

---

## Phase 10 — UX Polish (Low-Medium Impact)

### 10.1 Mobile-responsive map
- Sidebar collapses by default on screens < 768px
- Map controls enlarge to 44px touch targets
- Top bar shrinks to show only essential stats
- Add swipe-to-pan gesture hints

### 10.2 Keyboard accessibility
- Tab navigation through layer toggles and filters
- Enter/Space to toggle layers
- Escape to close popups/details panel
- Focus ring visible on all interactive elements

### 10.3 Loading states
- Skeleton loader for sidebar panels while data loads
- Progress bar for data fetch (bytes received / total)
- Spinner for Geojson source updates

### 10.4 Offline detection
- Show "offline" badge when `navigator.onLine` is false
- IndexedDB cache serves data; ArcGIS basemap won't load (show notice)
- Use a simple solid-color fallback when basemap tiles fail

---

## Phase 11 — Deployment & CI (Low-Medium Impact)

### 11.1 GitHub Actions CI
- On PR: `npm ci`, `npx tsc --noEmit`, `npm run build`
- On push to main: build + deploy to Vercel preview

### 11.2 Vercel config
- Ensure `public/data/*` and `public/tiles/*` are served with correct MIME types (`.pmtiles` → `application/octet-stream`)
- Set `Cache-Control` headers for data files

### 11.3 Environment-based config
- `VITE_MAPTILER_KEY` or similar for alternative basemaps
- `VITE_DATA_URL` to point at different data sources

---

## Summary

| Phase | Effort | Impact | Key Deliverable |
|-------|--------|--------|----------------|
| 5 — PMTiles Default | 3 days | **Massive** | 50K features rendered from vector tiles instead of GeoJSON |
| 6 — Search Navigation | 1 day | High | Click search result → map flies to asset |
| 7 — Testing | 2 days | Medium | CI guardrails, prevents regressions |
| 8 — Pipeline Automation | 1 day | Medium | One command to rebuild all data |
| 9 — Bundle Perf | 2 days | Medium | Cut initial bundle from 1MB to ~300KB |
| 10 — UX Polish | 2 days | Medium | Mobile + accessibility + loading states |
| 11 — Deployment | 1 day | Medium | Automated CI/CD pipeline |

**Priority recommendation:** Phase 5 first (PMTiles) — it's the biggest remaining bottleneck. Phase 6 next (search navigation) — closes the biggest UX gap. Then Phase 7 (tests) before any further refactoring.
