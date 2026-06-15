import { useState, useEffect, useMemo, useCallback, lazy, Suspense } from "react";
import SimpleAtlasMap from "./map/SimpleAtlasMap";
import PMTilesAtlasMap from "./map/PMTilesAtlasMap";
import ZoomableAtlasMap from "./map/ZoomableAtlasMap";
import ReliableAtlasMap from "./map/ReliableAtlasMap";
import GlobeAtlasMap from "./map/GlobeAtlasMap";
import type { CanvasDiagnostics } from "./map/InfrastructureCanvasOverlay";
import ErrorBoundary from "./components/ErrorBoundary";
import LayerPanel from "./components/LayerPanel";
import Legend from "./components/Legend";

const PUBLIC_STATIC_MODE = import.meta.env.VITE_PUBLIC_STATIC === "1";

const AtlasMap = lazy(() => import("./map/AtlasMap"));
const UsageMeter = PUBLIC_STATIC_MODE ? null : lazy(() => import("./components/UsageMeter"));
const PricingPage = PUBLIC_STATIC_MODE ? null : lazy(() => import("./components/PricingPage"));
const StatsDashboard = lazy(() => import("./components/StatsDashboard"));
const DataExport = lazy(() => import("./components/DataExport"));
const StatsPanel = lazy(() => import("./components/StatsPanel"));
const UnmappedPanel = lazy(() => import("./components/UnmappedPanel"));
const SourcePanel = lazy(() => import("./components/SourcePanel"));
const AssetDetailsPanel = lazy(() => import("./components/AssetDetailsPanel"));
const CommercialApiConsole = PUBLIC_STATIC_MODE ? null : lazy(() => import("./components/CommercialApiConsole"));
const SiteSelectionPanel = PUBLIC_STATIC_MODE ? null : lazy(() => import("./components/site_selection/SiteSelectionPanel"));
const LeadGenAsset = PUBLIC_STATIC_MODE ? null : lazy(() => import("./components/LeadGenAsset"));
import type { AtlasData, AtlasCore, FilterState, Asset, PowerPlant, Cable } from "./map/types";
import type { CandidateSite } from "./api/siteSelectionApi";
import type { InteractableType } from "./map/interaction";
import type { CableFilterState } from "./map/cables";
import { DEFAULT_CABLE_FILTERS, buildCableCompanyStats, cableBounds, splitCableOperators } from "./map/cables";
import type { LonLatBounds } from "./map/viewport";
import type { AtlasTheme } from "./utils/theme";
import { cachedFetch } from "./utils/cache";
import { isValidLonLat } from "./map/coords";
import { readUrlParams, writeUrlParams, layersToParam, paramToLayers } from "./utils/urlState";
import { toggleTheme, getTheme } from "./utils/theme";
import { DEFAULT_GRID_CONTINENT_FILTERS, type GridContinentFilters, type GridContinentKey } from "./map/continents";

import EnergyLegend from "./components/EnergyLegend";
import Curtain from "./components/Curtain";
import { calculateNearbyDestinations, buildFlowGeoJSON } from "./utils/energyFlowUtils";

type ViewMode = "map" | "globe";
const MAP_LAYER_KEYS = ["power_plants", "cables", "data_centers", "power_lines", "substations", "water_risk"] as const;

export default function App() {
  const queryParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const pathname = typeof window !== "undefined" ? window.location.pathname : "/";
  const commercialApiRoute =
    !PUBLIC_STATIC_MODE &&
    (
      queryParams.get("commercialApi") === "1" ||
      queryParams.get("apiConsole") === "1" ||
      queryParams.get("apiDashboard") === "1" ||
      pathname === "/api" ||
      pathname === "/api-dashboard"
    );
  const pricingRoute = !PUBLIC_STATIC_MODE && (queryParams.get("pricing") === "1" || pathname === "/pricing");
  const checkoutSuccess = queryParams.get("checkout") === "success" && queryParams.get("session_id");
  const checkoutCancelled = queryParams.get("checkout") === "cancelled";
  const initialParams = typeof window !== "undefined" ? readUrlParams() : {};
  const [data, setData] = useState<AtlasData | null>(null);
  const [core, setCore] = useState<AtlasCore | null>(null);
  const [powerLinesData, setPowerLinesData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [substationsData, setSubstationsData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(initialParams.sidebar !== "0");
  const [canvasDiag, setCanvasDiag] = useState<CanvasDiagnostics | null>(null);
  const [showTestPoints, setShowTestPoints] = useState(false);
  const [graticuleVisible, setGraticuleVisible] = useState(true);
  const [showDiagnostics, setShowDiagnostics] = useState(
    () => !PUBLIC_STATIC_MODE && typeof window !== "undefined" && new URLSearchParams(window.location.search).get("debug") === "1",
  );
  const [showCommercialWorkbench, setShowCommercialWorkbench] = useState(
    () => !PUBLIC_STATIC_MODE && typeof window !== "undefined" && new URLSearchParams(window.location.search).get("commercialPanel") === "1",
  );
  const [canvasEnabled, setCanvasEnabled] = useState(false);
  const [, setHoveredAssetId] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [selectedAssetType, setSelectedAssetType] = useState<InteractableType | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState(initialParams.searchQuery ?? "");
  const [navigateTo, setNavigateTo] = useState<{ lon: number; lat: number; zoom?: number; bounds?: LonLatBounds } | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [cableFilters, setCableFilters] = useState<CableFilterState>(DEFAULT_CABLE_FILTERS);
  const [viewMode, setViewMode] = useState<ViewMode>(() => queryParams.get("globe") === "1" ? "globe" : "map");
  const [theme, setTheme] = useState<AtlasTheme>(() => getTheme());
  const [gridContinentFilters, setGridContinentFilters] = useState<GridContinentFilters>(DEFAULT_GRID_CONTINENT_FILTERS);
  const [mapBounds, setMapBounds] = useState<[number, number, number, number] | null>(null);
  const [currentZoom, setCurrentZoom] = useState(0);
  const [showSiteSelection, setShowSiteSelection] = useState(false);
  const [showLeadGen, setShowLeadGen] = useState(false);
  const [siteSelectionAutoTrigger, setSiteSelectionAutoTrigger] = useState(false);
  const [candidateSites, setCandidateSites] = useState<CandidateSite[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSite | null>(null);
  const [energyLayerEnabled, setEnergyLayerEnabled] = useState(false);
  const [selectedEnergyFactory, setSelectedEnergyFactory] = useState<PowerPlant | null>(null);
  const [showEnergyFlows, setShowEnergyFlows] = useState(false);
  const [energyFlowGeoJSON, setEnergyFlowGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);

  const openApiDashboard = useCallback(() => {
    if (PUBLIC_STATIC_MODE) return;
    window.location.href = "/?commercialApi=1";
  }, []);

  const handleShare = useCallback(() => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopyFeedback("Copied!");
      setTimeout(() => setCopyFeedback(null), 2000);
    }).catch(() => {
      setCopyFeedback("Failed");
      setTimeout(() => setCopyFeedback(null), 2000);
    });
  }, []);

  const handleViewModeChange = useCallback((nextMode: ViewMode) => {
    setViewMode(nextMode);
    setCanvasDiag(null);
    writeUrlParams({ globe: nextMode === "globe" ? "1" : null });
  }, []);

  const [visibleLayers, setVisibleLayers] = useState(paramToLayers(initialParams.layers) ?? {
    power_plants: true,
    cables: true,
    data_centers: true,
    power_lines: true,
    substations: true,
    water_risk: false,
  });
  const [layerOpacity, setLayerOpacity] = useState<Record<string, number>>({
    power_plants: 0.85,
    cables: 0.85,
    data_centers: 0.9,
    power_lines: 0.7,
    substations: 0.85,
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const handlePopState = () => {
      setViewMode(new URLSearchParams(window.location.search).get("globe") === "1" ? "globe" : "map");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    if (PUBLIC_STATIC_MODE) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "D") {
        setShowDiagnostics((v) => !v);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleToggleTheme = useCallback(() => {
    setTheme(toggleTheme());
  }, []);

  const [filters, setFilters] = useState<FilterState>({
    fuelType: initialParams.fuelType ?? "",
    country: initialParams.country ?? "",
    minMw: initialParams.minMw ?? 0,
  });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      let loadedCore: AtlasCore | null = null;
      try {
        const coreResp = await fetch("/data/atlas_core.json", { signal: controller.signal });
        if (coreResp.ok) {
          const coreData: AtlasCore = await coreResp.json();
          loadedCore = coreData;
          setCore(coreData);
        }
      } catch {
        // atlas_core.json is metadata-only; the GeoJSON renderer can continue without it.
      }

      try {
        const webData = await cachedFetch<AtlasData>("/data/atlas_web_data.json", 5 * 60 * 1000);
        if (!webData.metadata || !webData.power_plants) {
          throw new Error("Invalid data structure: missing metadata or power_plants");
        }
        setData(webData);
        setLoading(false);
      } catch (err: unknown) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message);
          setLoading(false);
        }
      }

      const hasPowerLineTiles = loadedCore?.tile_registry?.power_lines?.status?.startsWith("present");
      if (!hasPowerLineTiles) {
        try {
          const resp = await fetch("/data/power_lines.json", { signal: controller.signal });
          if (resp.ok) {
            const plData: GeoJSON.FeatureCollection = await resp.json();
            if (plData.features?.length) setPowerLinesData(plData);
          }
        } catch {
          // power lines layer is optional; map works without it
        }
      }

      const hasSubstationTiles = loadedCore?.tile_registry?.substations?.status?.startsWith("present");
      if (!hasSubstationTiles) {
        try {
          const resp = await fetch("/data/substations.json", { signal: controller.signal });
          if (resp.ok) {
            const substationData: GeoJSON.FeatureCollection = await resp.json();
            if (substationData.features?.length) setSubstationsData(substationData);
          }
        } catch {
          // substations layer is optional; map works without it
        }
      }
    }

    load();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    writeUrlParams({
      fuel: filters.fuelType || null,
      country: filters.country || null,
      mw: filters.minMw > 0 ? filters.minMw : null,
      q: searchQuery || null,
      layers: layersToParam(visibleLayers),
      sidebar: sidebarOpen ? null : "0",
    });
  }, [filters, searchQuery, visibleLayers, sidebarOpen]);

  const fuelTypes = useMemo(() => {
    if (!data) return [];
    const s = new Set<string>();
    for (const p of data.power_plants) if (p.f) s.add(p.f);
    return Array.from(s).sort();
  }, [data]);

  const countries = useMemo(() => {
    if (!data) return [];
    const s = new Set<string>();
    for (const p of data.power_plants) if (p.c) s.add(p.c);
    return Array.from(s).sort();
  }, [data]);

  const cableCompanyStats = useMemo(() => {
    if (!data) return [];
    return buildCableCompanyStats(data.cables);
  }, [data]);

  const filteredPowerPlants = useMemo(() => {
    if (!data) return [];
    return data.power_plants.filter((p) => {
      if (filters.fuelType && p.f !== filters.fuelType) return false;
      if (filters.country && p.c !== filters.country) return false;
      if (filters.minMw > 0 && p.mw < filters.minMw) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!p.n.toLowerCase().includes(q) && !p.c.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [data, filters, searchQuery]);

  const visibleCount = useMemo(() => filteredPowerPlants.length, [filteredPowerPlants]);

  const searchResults = useMemo(() => {
    if (!data || !searchQuery) return [];
    const q = searchQuery.toLowerCase();
    const results: Array<{ label: string; type: string; asset: Asset }> = [];
    for (const p of data.power_plants) {
      if (p.n.toLowerCase().includes(q) || p.c.toLowerCase().includes(q)) {
        results.push({ label: `${p.n} (${p.c}, ${p.f})`, type: "power_plant", asset: p });
        if (results.length >= 50) break;
      }
    }
    if (results.length < 50) {
      for (const c of data.cables) {
        const operators = c.operators?.toLowerCase() || "";
        const landingPoints = Array.isArray(c.landing_points) ? c.landing_points.join(" ").toLowerCase() : (c.landing_points?.toLowerCase() || "");
        if (c.n.toLowerCase().includes(q) || operators.includes(q) || landingPoints.includes(q)) {
          const owner = c.operators?.split(",")[0]?.trim();
          results.push({ label: `${c.n}${owner ? ` (${owner})` : " (submarine cable)"}`, type: "cable", asset: c });
          if (results.length >= 50) break;
        }
      }
    }
    if (results.length < 50) {
      for (const d of data.data_centers) {
        if (d.n.toLowerCase().includes(q) || d.c.toLowerCase().includes(q) || d.city?.toLowerCase().includes(q)) {
          results.push({ label: `${d.n} (${d.city}, ${d.c})`, type: "data_center", asset: d });
          if (results.length >= 50) break;
        }
      }
    }
    return results;
  }, [data, searchQuery]);

  const counts = data ? data.metadata.counts : (core?.counts as Record<string, number> | null) || {};
  const cablesMapped = (counts?.cables_mapped ?? counts?.submarine_cables_mapped ?? 0) as number;
  const cablesTotal = (counts?.cables_total ?? counts?.submarine_cables_total ?? 0) as number;
  const dcsMapped = (counts?.data_centers_mapped ?? 0) as number;
  const dcsTotal = (counts?.data_centers_total ?? 0) as number;
  const ppTotal = (counts?.power_plants_mapped ?? 0) as number;
  const powerLinesMapped = (counts?.power_lines_mapped ?? 0) as number;
  const substationsMapped = (counts?.substations_mapped ?? 0) as number;
  const hasCoverageWarning = cablesMapped < cablesTotal || dcsMapped < dcsTotal;

  const activeFilterCount = useMemo(
    () => [filters.fuelType, filters.country, filters.minMw > 0 ? `${filters.minMw}+ MW` : ""].filter(Boolean).length,
    [filters]
  );

  const handleToggle = useCallback((key: string) => {
    setVisibleLayers((prev) => ({ ...prev, [key]: !(prev as Record<string, boolean>)[key] }));
  }, []);

  const handleSetAllLayers = useCallback((visible: boolean) => {
    setVisibleLayers((prev) => {
      const next = { ...prev };
      for (const key of MAP_LAYER_KEYS) next[key] = visible;
      return next;
    });
  }, []);

  const handleOpacityChange = useCallback((key: string, value: number) => {
    setLayerOpacity((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleGridContinentToggle = useCallback((key: GridContinentKey) => {
    setGridContinentFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  useEffect(() => {
    if (!showSiteSelection) setCandidateSites([]);
  }, [showSiteSelection]);

  const handlePopup = useCallback((asset: Asset | null) => {
    setSelectedAsset(asset);
    if (!asset) {
      setSelectedAssetId(null);
      setSelectedAssetType(null);
      setSelectedEnergyFactory(null);
    } else if (asset.kind === "power_plant") {
      setSelectedAssetType("power_plant");
    } else if (asset.kind === "data_center") {
      setSelectedAssetType("data_center");
    } else if (asset.kind === "power_line") {
      setSelectedAssetType("power_line");
    } else if (asset.kind === "substation") {
      setSelectedAssetType("substation");
    } else {
      setSelectedAssetType("submarine_cable");
      setCableFilters((prev) => ({ ...prev, selectedCableName: asset.n }));
    }
  }, []);

  const handleSelectedAsset = useCallback((id: string | null) => {
    setSelectedAssetId(id);
  }, []);

  const handleCloseDetails = useCallback(() => {
    setSelectedAsset(null);
    setSelectedAssetId(null);
    setSelectedAssetType(null);
    setSelectedEnergyFactory(null);
    setShowEnergyFlows(false);
    setEnergyFlowGeoJSON(null);
  }, []);

  const handleEnergyFactorySelect = useCallback((plant: PowerPlant | null) => {
    setSelectedEnergyFactory(plant);
    if (plant && data && showEnergyFlows) {
      const destinations = calculateNearbyDestinations(plant, data);
      setEnergyFlowGeoJSON(buildFlowGeoJSON(plant, destinations));
    } else {
      setEnergyFlowGeoJSON(null);
    }
  }, [data, showEnergyFlows]);

  const handleToggleEnergyFlows = useCallback((plant?: PowerPlant | null) => {
    const p = plant || selectedEnergyFactory;
    setShowEnergyFlows((prev) => {
      const next = !prev;
      if (next && p && data) {
        const destinations = calculateNearbyDestinations(p, data);
        setEnergyFlowGeoJSON(buildFlowGeoJSON(p, destinations));
      } else {
        setEnergyFlowGeoJSON(null);
      }
      return next;
    });
    if (plant) setSelectedEnergyFactory(plant);
  }, [selectedEnergyFactory, data]);

  function getCableFirstCoord(cable: Cable): [number, number] | null {
    const g = cable.geometry;
    if (!g) return null;
    if (Array.isArray(g[0]) && Array.isArray(g[0][0])) {
      const multi = g as number[][][];
      if (multi.length > 0 && multi[0].length > 0) return multi[0][0] as [number, number];
    }
    if (Array.isArray(g[0])) {
      const single = g as number[][];
      if (single.length > 0) return single[0] as [number, number];
    }
    return null;
  }

  const handleSearchResultClick = useCallback((asset: Asset) => {
    handlePopup(asset);
    if (asset.kind === "power_plant" || asset.kind === "data_center") {
      if (isValidLonLat(asset.lon, asset.lat)) {
        setNavigateTo({ lon: asset.lon, lat: asset.lat, zoom: 10 });
      }
    } else if (asset.kind === "submarine_cable") {
      const coord = getCableFirstCoord(asset);
      if (coord) {
        setNavigateTo({ lon: coord[0], lat: coord[1], zoom: 5 });
      }
      setCableFilters((prev) => ({ ...prev, selectedCableName: asset.n }));
    }
  }, [handlePopup]);

  const handleFitCableFocus = useCallback(() => {
    if (!data) return;
    let focused = data.cables;
    if (cableFilters.selectedCableName) {
      focused = focused.filter((c) => c.n === cableFilters.selectedCableName);
    } else if (cableFilters.operator) {
      const operator = cableFilters.operator.toLowerCase();
      focused = focused.filter((c) => splitCableOperators(c.operators).some((op) => op.toLowerCase() === operator));
    }

    const bounds = focused
      .map((c) => cableBounds(c.geometry))
      .filter(Boolean) as LonLatBounds[];
    if (!bounds.length) return;
    const merged: LonLatBounds = {
      minLon: Math.min(...bounds.map((b) => b.minLon)),
      minLat: Math.min(...bounds.map((b) => b.minLat)),
      maxLon: Math.max(...bounds.map((b) => b.maxLon)),
      maxLat: Math.max(...bounds.map((b) => b.maxLat)),
    };
    setNavigateTo({ lon: 0, lat: 0, bounds: merged });
  }, [data, cableFilters]);

  const handleFitAsset = useCallback((asset: Asset) => {
    if (asset.kind === "submarine_cable") {
      const sourceCable = data?.cables.find((c) => c.n === asset.n);
      const bounds = cableBounds(asset.geometry) || cableBounds(sourceCable?.geometry);
      if (bounds) {
        setNavigateTo({ lon: 0, lat: 0, bounds });
        setCableFilters((prev) => ({ ...prev, selectedCableName: asset.n, mode: "selected" }));
        return;
      }
    }
    if ((asset.kind === "power_plant" || asset.kind === "data_center") && isValidLonLat(asset.lon, asset.lat)) {
      setNavigateTo({ lon: asset.lon, lat: asset.lat, zoom: 10 });
    }
  }, [data]);

  const handleBoundsChanged = useCallback((bounds: [number, number, number, number]) => {
    setMapBounds(bounds);
  }, []);
  const handleZoomChanged = useCallback((zoom: number) => {
    setCurrentZoom(zoom);
  }, []);

  const handleCandidateClick = useCallback((candidate: CandidateSite) => {
    setSelectedCandidate(candidate);
    setNavigateTo({ lon: candidate.lon, lat: candidate.lat, zoom: 12 });
  }, []);

  const hasZeroCanvasPoints = viewMode !== "globe" && Boolean(
    canvasDiag?.active && data && canvasDiag.powerPlantsDrawn === 0 && canvasDiag.recordsReceived > 1000
  );

  if (pricingRoute && PricingPage) {
    return (
      <Suspense fallback={<div className="app"><div className="loading-screen"><div className="loading-spinner" /><div className="loading-text">Loading pricing...</div></div></div>}>
        <PricingPage
          onClose={() => { window.location.href = "/"; }}
          checkoutSuccess={checkoutSuccess ? { sessionId: checkoutSuccess, plan: "" } : null}
          checkoutCancelled={checkoutCancelled}
        />
      </Suspense>
    );
  }

  if (commercialApiRoute && CommercialApiConsole) {
    return (
      <Suspense fallback={<div className="app"><div className="loading-screen"><div className="loading-spinner" /><div className="loading-text">Loading API dashboard...</div></div></div>}>
        <CommercialApiConsole onClose={() => { window.location.href = "/"; }} />
      </Suspense>
    );
  }

  if (loading) {
    return (
      <div className="app">
        <div className="loading-screen">
          <div className="loading-brand">FUTURE Infrastructure Intelligence</div>
          <div className="loading-spinner" />
          <div className="loading-text">Loading infrastructure intelligence...</div>
          <div className="loading-sub">The decision layer for AI compute, energy, and data-center infrastructure site selection.</div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="app">
        <div className="error-screen">
          <div className="error-icon">!</div>
          <div className="error-title">Data file missing or invalid</div>
          <div className="error-message">{error || "No data available"}</div>
          <div className="error-hint">Ensure atlas_web_data.json exists in the public data directory and is valid JSON.</div>
          <div className="error-footer"><Suspense fallback={null}><SourcePanel metadata={null} core={core ?? undefined} /></Suspense></div>
        </div>
      </div>
    );
  }

  const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const debugMap = !PUBLIC_STATIC_MODE && params.get("debugMap") === "1";
  const zoomMap = !PUBLIC_STATIC_MODE && params.get("zoomMap") === "1";
  const reliableMap = !PUBLIC_STATIC_MODE && params.get("reliableMap") === "1";
  const maplibreMap = !PUBLIC_STATIC_MODE && params.get("maplibreMap") === "1";
  const pmtilesMap = !PUBLIC_STATIC_MODE && params.get("pmtilesMap") === "1";
  const globeMap = viewMode === "globe";
  const proof = !PUBLIC_STATIC_MODE && params.get("proof") === "1";
  const canvasFallback = !PUBLIC_STATIC_MODE && params.get("canvasFallback") === "1";
  const embed = params.get("embed") === "1";

  if (pmtilesMap) {
    if (core) return <ErrorBoundary><PMTilesAtlasMap core={core} /></ErrorBoundary>;
    return (
      <div className="app">
        <div className="error-screen">
          <div className="error-icon">!</div>
          <div className="error-title">PMTiles metadata unavailable</div>
          <div className="error-message">atlas_core.json is required for the PMTiles route.</div>
          <div className="error-hint">Run python scripts/build_atlas_core.py and reload this route.</div>
        </div>
      </div>
    );
  }

  if (debugMap) {
    return <ErrorBoundary><SimpleAtlasMap data={data} /></ErrorBoundary>;
  }

  if (zoomMap) {
    return <ZoomMapRoute data={data} proof={proof} />;
  }

  if (maplibreMap) {
    return <ReliableMapRoute data={data} proof={proof} />;
  }

  if (reliableMap) {
    return <ReliableMapRoute data={data} proof={proof} />;
  }

  if (embed) {
    return (
      <ErrorBoundary>
        <div className="app app-shell app-shell--embed">
          <div className="map-area map-stage" style={{ width: "100%", height: "100%" }}>
            <Suspense fallback={<div className="loading-screen"><div className="loading-spinner"></div><div className="loading-text">Loading map...</div></div>}>
              <AtlasMap
              key={`embed-${theme}`}
              data={data}
              filters={filters}
              visibleLayers={visibleLayers}
              onPopup={handlePopup}
              onCanvasDiagnostics={setCanvasDiag}
              showTestPoints={showTestPoints}
              graticuleVisible={false}
              onHoveredAsset={setHoveredAssetId}
              onSelectedAsset={handleSelectedAsset}
              selectedAssetId={selectedAssetId}
              canvasEnabled={canvasEnabled || canvasFallback}
              core={core ?? undefined}
              navigateTo={navigateTo}
              layerOpacity={layerOpacity}
              powerLinesData={powerLinesData}
              substationsData={substationsData}
              cableCompanyStats={cableCompanyStats}
              cableFilters={cableFilters}
              theme={theme}
              />
            </Suspense>
          </div>
        </div>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="app app-shell">
        {/* ─── Map (full viewport) ─── */}
        <div className="map-area map-stage">

          {/* Floating top bar */}
          <div className="floating-topbar">
            <span className="floating-topbar-title">FUTURE</span>
            <span className="top-bar-position">AI compute site intelligence</span>
            {UsageMeter && <UsageMeter />}
            {!PUBLIC_STATIC_MODE && (
              <>
                <button className="top-bar-api-link" type="button" onClick={openApiDashboard}>
                  Enterprise API
                </button>
                <button className="top-bar-api-link pricing-link" type="button" onClick={() => { window.location.href = "/?pricing=1"; }}>
                  Pricing
                </button>
              </>
            )}
            <div className="view-mode-switch" role="group" aria-label="Map view mode">
              <button type="button" className={`view-mode-option ${viewMode === "map" ? "active" : ""}`} onClick={() => handleViewModeChange("map")} aria-pressed={viewMode === "map"}>Map</button>
              <button type="button" className={`view-mode-option ${viewMode === "globe" ? "active" : ""}`} onClick={() => handleViewModeChange("globe")} aria-pressed={viewMode === "globe"}>Globe</button>
            </div>
            <span className="top-bar-stat">{ppTotal.toLocaleString()} power plants</span>
            <span className="top-bar-stat">{powerLinesMapped.toLocaleString()} lines</span>
            <span className="top-bar-stat">{substationsMapped.toLocaleString()} substations</span>
            <span className="top-bar-stat">{cablesMapped.toLocaleString()} / {cablesTotal.toLocaleString()} cables</span>
            <span className="top-bar-stat">{dcsMapped.toLocaleString()} / {dcsTotal.toLocaleString()} data centers</span>
            {activeFilterCount > 0 && <span className="top-bar-filter-badge">{activeFilterCount} filter{activeFilterCount > 1 ? "s" : ""} active</span>}
            {hasCoverageWarning && <span className="top-bar-warning-badge">Partial coverage</span>}
            {viewMode === "map" && canvasDiag?.active && canvasDiag.projectionMode && <span className="top-bar-stat">{canvasDiag.projectionMode}</span>}
            {hasZeroCanvasPoints && <span className="top-bar-warning-badge">0 points drawn</span>}
            <button className="toolbar-btn" onClick={handleToggleTheme} title="Toggle dark/light theme">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
            </button>
            <button className="toolbar-btn" onClick={handleShare} title="Copy share link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
            </button>
            {copyFeedback && <span className="top-bar-share-feedback">{copyFeedback}</span>}
          </div>

          {/* FABs */}
          <button
            className={`floating-fab floating-fab--layers ${sidebarOpen ? "active" : ""}`}
            onClick={() => setSidebarOpen((v) => !v)}
            title="Toggle layer catalog"
            aria-label="Toggle layer catalog"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
          </button>
          <button
            className={`floating-fab floating-fab--analytics ${!!selectedAsset ? "active" : ""}`}
            onClick={() => { if (selectedAsset) handleCloseDetails(); }}
            title="Contextual analytics"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
          </button>

          {/* Coverage warnings */}
          {hasCoverageWarning && (
            <div className="coverage-warning" style={{ position: "absolute", top: "72px", left: "64px", zIndex: 20, maxWidth: "400px" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01M12 2l10 18H2L12 2z"/></svg>
              <span>Some infrastructure layers have limited mapped coverage. Cables: {cablesMapped}/{cablesTotal} mapped. Data centers: {dcsMapped}/{dcsTotal} mapped.</span>
            </div>
          )}
          {hasZeroCanvasPoints && (
            <div className="coverage-warning" style={{ position: "absolute", top: hasCoverageWarning ? "102px" : "72px", left: "64px", zIndex: 20, maxWidth: "400px", borderTop: "1px solid rgba(200,50,50,0.2)" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01M12 2l10 18H2L12 2z"/></svg>
              <span>Visible points in current viewport: 0. Valid coordinates loaded: {canvasDiag?.validCoords?.toLocaleString()}. Camera may be outside data bounds.</span>
            </div>
          )}

          {/* Power plant toggle */}
          <button
            type="button"
            className={`power-plant-view-toggle ${visibleLayers.power_plants ? "active" : ""}`}
            onClick={() => handleToggle("power_plants")}
            aria-pressed={Boolean(visibleLayers.power_plants)}
            title={visibleLayers.power_plants ? "Hide power plants" : "Show power plants"}
            style={{ position: "absolute", top: "70px", left: "64px", zIndex: 20 }}
          >
            <span className="power-plant-view-toggle__dot" />
            <span>{visibleLayers.power_plants ? "Power Plants On" : "Power Plants Off"}</span>
          </button>

          {/* Map */}
          {globeMap ? (
            <div className="map-container" style={{ width: "100%", height: "100%" }}>
              <GlobeAtlasMap
                key={`globe-${theme}`}
                data={data}
                filters={filters}
                visibleLayers={visibleLayers}
                graticuleVisible={graticuleVisible}
                proof={proof}
                onAssetSelect={handlePopup}
                cableCompanyStats={cableCompanyStats}
                cableFilters={cableFilters}
                navigateTo={navigateTo}
                core={core ?? undefined}
                powerLinesData={powerLinesData}
                layerOpacity={layerOpacity}
                gridContinentFilters={gridContinentFilters}
                theme={theme}
              />
            </div>
          ) : reliableMap ? (
            <div className="map-container" style={{ width: "100%", height: "100%" }}>
              <ReliableAtlasMap
                data={data}
                filters={filters}
                visibleLayers={visibleLayers}
                graticuleVisible={graticuleVisible}
                onAssetSelect={handlePopup}
                cableCompanyStats={cableCompanyStats}
                cableFilters={cableFilters}
              />
            </div>
          ) : (
            <Suspense fallback={<div className="loading-screen" style={{ position: "absolute", inset: 0 }}><div className="loading-spinner"></div><div className="loading-text">Loading map...</div></div>}>
              <AtlasMap
                key={`atlas-${theme}`}
                data={data}
                filters={filters}
                visibleLayers={visibleLayers}
                onPopup={handlePopup}
                onCanvasDiagnostics={setCanvasDiag}
                showTestPoints={showTestPoints}
                graticuleVisible={graticuleVisible}
                onHoveredAsset={setHoveredAssetId}
                onSelectedAsset={handleSelectedAsset}
                selectedAssetId={selectedAssetId}
                canvasEnabled={canvasEnabled || canvasFallback}
                core={core ?? undefined}
                navigateTo={navigateTo}
                layerOpacity={layerOpacity}
                powerLinesData={powerLinesData}
                substationsData={substationsData}
                cableCompanyStats={cableCompanyStats}
                cableFilters={cableFilters}
                theme={theme}
                onBoundsChanged={handleBoundsChanged}
                onZoomChanged={handleZoomChanged}
                candidateSites={candidateSites}
                analysisBounds={candidateSites.length > 0 ? mapBounds : null}
                onCandidateClick={handleCandidateClick}
                energyLayerEnabled={energyLayerEnabled}
                selectedEnergyFactory={selectedEnergyFactory}
                onEnergyFactorySelect={handleEnergyFactorySelect}
                energyFlowGeoJSON={energyFlowGeoJSON}
              />
            </Suspense>
          )}

          {/* Diagnostics */}
          <DiagnosticsPanel
            canvasDiag={canvasDiag}
            showTestPoints={showTestPoints}
            onToggleTestPoints={setShowTestPoints}
            visible={!PUBLIC_STATIC_MODE && showDiagnostics}
            canvasEnabled={canvasEnabled}
            onToggleCanvas={setCanvasEnabled}
            onClose={() => setShowDiagnostics(false)}
          />

          {/* Commercial workbench overlay */}
          {!PUBLIC_STATIC_MODE && showCommercialWorkbench && CommercialApiConsole && (
            <div className="commercial-map-overlay" role="dialog" aria-modal="true" aria-label="Commercial API workbench">
              <Suspense fallback={<div className="commercial-map-loading">Loading API workbench...</div>}>
                <CommercialApiConsole embedded onClose={() => setShowCommercialWorkbench(false)} />
              </Suspense>
            </div>
          )}

          {/* Analyze area button */}
          {!PUBLIC_STATIC_MODE && currentZoom >= 8 && !showSiteSelection && viewMode !== "globe" && candidateSites.length === 0 && (
            <div className="analyze-area-btn-container">
              <button className="analyze-area-btn" onClick={() => { setShowSiteSelection(true); setSiteSelectionAutoTrigger(true); }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
                  <circle cx="12" cy="10" r="3"/>
                </svg>
                Run Compute Site Selection
              </button>
            </div>
          )}

          {/* Toolbar in top-right (theme, share, graticule, etc.) */}
          <div style={{ position: "absolute", top: "16px", right: "16px", zIndex: 25, display: "flex", gap: "6px" }}>
            <button className={`toolbar-btn ${graticuleVisible ? "active" : ""}`} onClick={() => setGraticuleVisible((v) => !v)} title="Toggle graticule">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2v20"/></svg>
            </button>
            {!PUBLIC_STATIC_MODE && (showDiagnostics || new URLSearchParams(window.location.search).get("debug") === "1") && (
              <>
                <button className={`toolbar-btn toolbar-btn--canvas ${canvasEnabled || canvasFallback ? "active" : ""}`} onClick={() => setCanvasEnabled((v) => !v)} title="Toggle canvas overlay">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/></svg>
                </button>
                <button className={`toolbar-btn ${showDiagnostics ? "active" : ""}`} onClick={() => setShowDiagnostics((v) => !v)} title="Toggle diagnostics">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>
                </button>
              </>
            )}
            {!PUBLIC_STATIC_MODE && (
              <>
                <button className={`toolbar-btn toolbar-btn--commercial ${showCommercialWorkbench ? "active" : ""}`} onClick={() => setShowCommercialWorkbench((v) => !v)} title="Open commercial API and pricing workbench">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"/><path d="M4 7v5c0 1.7 3.6 3 8 3s8-1.3 8-3V7"/><path d="M4 12v5c0 1.7 3.6 3 8 3s8-1.3 8-3v-5"/></svg>
                </button>
                <button className={`toolbar-btn ${showSiteSelection ? "active" : ""}`} onClick={() => setShowSiteSelection((v) => !v)} title="Site selection analysis">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
                </button>
                <button className={`toolbar-btn ${showLeadGen ? "active" : ""}`} onClick={() => setShowLeadGen((v) => !v)} title="Sample site selection report (lead gen)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                </button>
              </>
            )}
          </div>
        </div>

        {/* ─── Left Curtain (Layer Catalog) ─── */}
        <Curtain side="left" open={sidebarOpen} onClose={() => setSidebarOpen(false)} width={380}>
          <div className="curtain-header">
            <h2>FUTURE Infrastructure Intelligence</h2>
            <button className="curtain-close" onClick={() => setSidebarOpen(false)} title="Close panel">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <div className="curtain-section">
            <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "10px", lineHeight: 1.55 }}>
              Decision-grade geospatial intelligence for AI compute, energy, network reach, water risk, and data-center site selection.
            </div>
            {!PUBLIC_STATIC_MODE && (
              <>
                <div className="decision-mode-buttons">
                  <button className="decision-btn decision-btn--primary" type="button" onClick={() => { setShowSiteSelection(true); setSidebarOpen(true); }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    <span>Run Site Selection</span>
                  </button>
                  <button className="decision-btn decision-btn--secondary" type="button" onClick={() => { setShowSiteSelection(false); }}>
                    Explore Infrastructure
                  </button>
                </div>
                <button className="api-dashboard-link" type="button" onClick={openApiDashboard}>
                  <span>Enterprise Data &amp; API</span>
                  <strong>Pricing, keys, exports &amp; institutional access</strong>
                </button>
                <button className="api-dashboard-link pricing-link" type="button" onClick={() => { window.location.href = "/?pricing=1"; }}>
                  <span>Pricing &amp; Plans</span>
                  <strong>Launch $299/mo · Scale $1,250/mo · Enterprise $4,900+/mo</strong>
                </button>
              </>
            )}
          </div>
          <LayerPanel
            visibleLayers={visibleLayers}
            onToggle={handleToggle}
            onSetAllLayers={handleSetAllLayers}
            filters={filters}
            onFilterChange={setFilters}
            fuelTypes={fuelTypes}
            countries={countries}
            counts={data.metadata.counts}
            visibleCount={visibleCount}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            searchResults={searchResults}
            onSearchResultClick={handleSearchResultClick}
            layerOpacity={layerOpacity}
            onOpacityChange={handleOpacityChange}
            cableCompanyStats={cableCompanyStats}
            cableFilters={cableFilters}
            onCableFiltersChange={setCableFilters}
            onFitCables={handleFitCableFocus}
            showGridContinentControls={globeMap}
            gridContinentFilters={gridContinentFilters}
            onGridContinentToggle={handleGridContinentToggle}
            energyLayerEnabled={energyLayerEnabled}
            onEnergyToggle={() => setEnergyLayerEnabled((v) => !v)}
          />
          <Suspense fallback={<div className="curtain-section"><div className="panel-loading">Loading...</div></div>}>
            <StatsDashboard data={data} filters={filters} />
          </Suspense>
          <div className="curtain-section">
            <Legend cableCompanyStats={cableCompanyStats} cableFilters={cableFilters} />
            <EnergyLegend />
          </div>
          <Suspense fallback={null}>
            <StatsPanel metadata={data.metadata} />
          </Suspense>
          <Suspense fallback={null}>
            <DataExport data={data} filters={filters} />
          </Suspense>
          <Suspense fallback={null}>
            <UnmappedPanel metadata={data.metadata} />
          </Suspense>
          <Suspense fallback={null}>
            <SourcePanel metadata={data.metadata} core={core ?? undefined} />
          </Suspense>
          {!PUBLIC_STATIC_MODE && showSiteSelection && SiteSelectionPanel && (
            <Suspense fallback={<div className="curtain-section"><div className="panel-loading">Loading site selection...</div></div>}>
              <SiteSelectionPanel
                mapBounds={mapBounds}
                onCandidatesGenerated={setCandidateSites}
                autoTrigger={siteSelectionAutoTrigger}
                onAutoTriggerConsumed={() => setSiteSelectionAutoTrigger(false)}
              />
            </Suspense>
          )}
          {!PUBLIC_STATIC_MODE && showLeadGen && LeadGenAsset && (
            <Suspense fallback={<div className="curtain-section"><div className="panel-loading">Loading report...</div></div>}>
              <LeadGenAsset onClose={() => setShowLeadGen(false)} />
            </Suspense>
          )}
          <div className="curtain-section" style={{ fontSize: "10px", color: "var(--text-muted)", textAlign: "center", padding: "16px" }}>
            Generated {new Date(data.metadata.generated_at).toLocaleString()}
          </div>
        </Curtain>

        {/* ─── Right Curtain (Contextual Analytics) ─── */}
        <Curtain side="right" open={!!selectedAsset} onClose={handleCloseDetails} width={420}>
          <div className="curtain-header">
            <h2>Asset Details</h2>
            <button className="curtain-close" onClick={handleCloseDetails} title="Close panel">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <div className="curtain-inner">
            <Suspense fallback={<div className="curtain-section"><div className="panel-loading">Loading details...</div></div>}>
              <AssetDetailsPanel
                asset={selectedAsset}
                assetType={selectedAssetType}
                onClose={handleCloseDetails}
                onFitAsset={handleFitAsset}
                showEnergyFlows={showEnergyFlows}
                onToggleEnergyFlows={handleToggleEnergyFlows}
              />
            </Suspense>
          </div>
        </Curtain>
      </div>
    </ErrorBoundary>
  );
}

function GlobeMapRoute({ data, proof }: { data: AtlasData; proof?: boolean }) {
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [selectedAssetType, setSelectedAssetType] = useState<InteractableType | null>(null);
  const [navigateTo, setNavigateTo] = useState<{ lon: number; lat: number; zoom?: number; bounds?: LonLatBounds } | null>(null);
  const [showCommercialWorkbench, setShowCommercialWorkbench] = useState(
    () => !PUBLIC_STATIC_MODE && typeof window !== "undefined" && new URLSearchParams(window.location.search).get("commercialPanel") === "1",
  );
  const visibleLayers = useMemo(() => ({ power_plants: true, cables: true, data_centers: true }), []);
  const filters = useMemo(() => ({ fuelType: "", country: "", minMw: 0 }), []);
  const cableCompanyStats = useMemo(() => buildCableCompanyStats(data.cables), [data]);
  const cableFilters = useMemo(() => DEFAULT_CABLE_FILTERS, []);

  const handlePopup = useCallback((asset: Asset | null, assetType: InteractableType | null) => {
    setSelectedAsset(asset);
    setSelectedAssetType(asset ? assetType : null);
  }, []);

  const handleFitAsset = useCallback((asset: Asset) => {
    if (asset.kind === "submarine_cable") {
      const sourceCable = data.cables.find((c) => c.n === asset.n);
      const bounds = cableBounds(asset.geometry) || cableBounds(sourceCable?.geometry);
      if (bounds) {
        setNavigateTo({ lon: 0, lat: 0, bounds });
      }
      return;
    }
    if ((asset.kind === "power_plant" || asset.kind === "data_center") && isValidLonLat(asset.lon, asset.lat)) {
      setNavigateTo({ lon: asset.lon, lat: asset.lat, zoom: 4.5 });
    }
  }, [data]);

  return (
    <ErrorBoundary>
      <div className="app app-shell app-shell--map-only">
        <div className="map-area map-stage">
          <div className="map-container">
            <GlobeAtlasMap
              data={data}
              filters={filters}
              visibleLayers={visibleLayers}
              proof={proof}
              onAssetSelect={handlePopup}
              cableCompanyStats={cableCompanyStats}
              cableFilters={cableFilters}
              navigateTo={navigateTo}
            />
          </div>
          {!PUBLIC_STATIC_MODE && (
            <button
              className={`globe-commercial-button ${showCommercialWorkbench ? "active" : ""}`}
              type="button"
              onClick={() => setShowCommercialWorkbench((v) => !v)}
              title="Open commercial API and pricing workbench"
            >
              API
            </button>
          )}
          <Suspense fallback={null}>
            <AssetDetailsPanel
              asset={selectedAsset}
              assetType={selectedAssetType}
              onClose={() => handlePopup(null, null)}
              onFitAsset={handleFitAsset}
            />
          </Suspense>
          {!PUBLIC_STATIC_MODE && showCommercialWorkbench && CommercialApiConsole && (
            <div className="commercial-map-overlay commercial-map-overlay--globe" role="dialog" aria-modal="true" aria-label="Commercial API workbench">
              <Suspense fallback={<div className="commercial-map-loading">Loading API workbench...</div>}>
                <CommercialApiConsole embedded onClose={() => setShowCommercialWorkbench(false)} />
              </Suspense>
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
}

function ReliableMapRoute({ data, proof }: { data: AtlasData; proof?: boolean }) {
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [selectedAssetType, setSelectedAssetType] = useState<InteractableType | null>(null);
  const visibleLayers = useMemo(() => ({ power_plants: true, cables: true, data_centers: true }), []);
  const filters = useMemo(() => ({ fuelType: "", country: "", minMw: 0 }), []);
  const cableCompanyStats = useMemo(() => buildCableCompanyStats(data.cables), [data]);
  const cableFilters = useMemo(() => DEFAULT_CABLE_FILTERS, []);

  const handlePopup = useCallback((asset: Asset | null, assetType: InteractableType | null) => {
    setSelectedAsset(asset);
    setSelectedAssetType(asset ? assetType : null);
  }, []);

  return (
    <ErrorBoundary>
      <div className="app app-shell app-shell--map-only">
        <div className="map-area map-stage">
          <div className="map-container">
            <ReliableAtlasMap
              data={data}
              filters={filters}
              visibleLayers={visibleLayers}
              proof={proof}
              onAssetSelect={handlePopup}
              cableCompanyStats={cableCompanyStats}
              cableFilters={cableFilters}
            />
          </div>
          <Suspense fallback={null}>
            <AssetDetailsPanel asset={selectedAsset} assetType={selectedAssetType} onClose={() => handlePopup(null, null)} />
          </Suspense>
        </div>
      </div>
    </ErrorBoundary>
  );
}

function ZoomMapRoute({ data, proof }: { data: AtlasData; proof?: boolean }) {
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [selectedAssetType, setSelectedAssetType] = useState<InteractableType | null>(null);
  const visibleLayers = useMemo(() => ({ power_plants: true, cables: true, data_centers: true }), []);
  const filters = useMemo(() => ({ fuelType: "", country: "", minMw: 0 }), []);
  const cableCompanyStats = useMemo(() => buildCableCompanyStats(data.cables), [data]);
  const cableFilters = useMemo(() => DEFAULT_CABLE_FILTERS, []);

  const handlePopup = useCallback((asset: Asset | null, assetType: InteractableType | null) => {
    setSelectedAsset(asset);
    setSelectedAssetType(asset ? assetType : null);
  }, []);

  return (
    <ErrorBoundary>
      <div className="app app-shell app-shell--map-only">
        <div className="map-area map-stage">
          <div className="map-container">
            <ZoomableAtlasMap
              data={data}
              filters={filters}
              visibleLayers={visibleLayers}
              proof={proof}
              onAssetSelect={handlePopup}
              cableCompanyStats={cableCompanyStats}
              cableFilters={cableFilters}
            />
          </div>
          <Suspense fallback={null}>
            <AssetDetailsPanel asset={selectedAsset} assetType={selectedAssetType} onClose={() => handlePopup(null, null)} />
          </Suspense>
        </div>
      </div>
    </ErrorBoundary>
  );
}

function DiagnosticsPanel({
  canvasDiag,
  showTestPoints,
  onToggleTestPoints,
  visible,
  canvasEnabled,
  onToggleCanvas,
  onClose,
}: {
  canvasDiag: CanvasDiagnostics | null;
  showTestPoints: boolean;
  onToggleTestPoints: (v: boolean) => void;
  visible: boolean;
  canvasEnabled: boolean;
  onToggleCanvas: (v: boolean) => void;
  onClose?: () => void;
}) {
  if (!visible) return null;

  if (!canvasDiag) {
    return (
      <div className="diag-panel">
        <div className="diag-panel-header">
          <span>Renderer Diagnostics</span>
          <span className="diag-panel-close" onClick={() => onClose?.()} style={{ cursor: "pointer", opacity: 0.5 }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </span>
        </div>
        <div className="diag-summary">
          <div className="diag-row">
            <span className="diag-label">Renderer</span>
            <span className="diag-val ok">Clean MapLibre</span>
          </div>
          <div className="diag-row">
            <span className="diag-label">Canvas fallback</span>
            <span className="diag-val">
              <label style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                <input type="checkbox" checked={canvasEnabled} onChange={(e) => onToggleCanvas(e.target.checked)} style={{ accentColor: "#d69a13", width: 11, height: 11 }} />
                <span style={{ color: canvasEnabled ? "#d69a13" : "#5a5a62", fontSize: 9 }}>{canvasEnabled ? "enabled" : "disabled"}</span>
              </label>
            </span>
          </div>
          <div className="diag-row">
            <span className="diag-label">Fallback URL</span>
            <span className="diag-val">?canvasFallback=1</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="diag-panel">
      <div className="diag-panel-header">
        <span>Renderer Diagnostics</span>
        <span className="diag-panel-close" onClick={() => onClose?.()} style={{ cursor: "pointer", opacity: 0.5 }}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </span>
      </div>
      <div className="diag-summary">
        <div className="diag-row">
          <span className="diag-label">Canvas active</span>
          <span className={`diag-val ${canvasDiag.active ? "ok" : "fail"}`}>{canvasDiag.active ? "yes" : "no"}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Map area</span>
          <span className="diag-val">{canvasDiag.canvasWidth} &times; {canvasDiag.canvasHeight}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Zoom level</span>
          <span className={`diag-val ${canvasDiag.currentZoom > 0 && canvasDiag.currentZoom < 8 ? "ok" : "fail"}`}>
            {canvasDiag.currentZoom.toFixed(1)}
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Records received</span>
          <span className="diag-val">{canvasDiag.recordsReceived.toLocaleString()}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Valid coordinates</span>
          <span className={`diag-val ${canvasDiag.validCoords > 1000 ? "ok" : "fail"}`}>{canvasDiag.validCoords.toLocaleString()}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Visible in viewport</span>
          <span className={`diag-val ${canvasDiag.powerPlantsDrawn > 1000 ? "ok" : "fail"}`}>{canvasDiag.powerPlantsDrawn.toLocaleString()}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Cables drawn</span>
          <span className="diag-val">{canvasDiag.cableLinesDrawn}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Data centers drawn</span>
          <span className="diag-val">{canvasDiag.dataCentersDrawn}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Test points drawn</span>
          <span className="diag-val">{canvasDiag.testPointsDrawn}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Projection</span>
          <span className="diag-val">{canvasDiag.projectionMode}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Last draw</span>
          <span className="diag-val">{new Date(canvasDiag.lastDrawTime).toLocaleTimeString()}</span>
        </div>
        {canvasDiag.lastError && (
          <div className="diag-row">
            <span className="diag-label">Error</span>
            <span className="diag-val fail">{canvasDiag.lastError}</span>
          </div>
        )}
        <div className="diag-row">
          <span className="diag-label">Renderer</span>
          <span className="diag-val ok" style={{ fontSize: 9 }}>MapLibre layers</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Canvas fallback</span>
          <span className="diag-val">
            <label style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
              <input type="checkbox" checked={canvasEnabled} onChange={(e) => onToggleCanvas(e.target.checked)} style={{ accentColor: "#d69a13", width: 11, height: 11 }} />
              <span style={{ color: canvasEnabled ? "#d69a13" : "#5a5a62", fontSize: 9 }}>{canvasEnabled ? "enabled" : "disabled"}</span>
            </label>
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Test mode</span>
          <span className="diag-val">
            <label style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
              <input type="checkbox" checked={showTestPoints} onChange={(e) => onToggleTestPoints(e.target.checked)} style={{ accentColor: "#d69a13", width: 11, height: 11 }} />
              <span style={{ color: "#8d93a1", fontSize: 9 }}>5 test cities</span>
            </label>
          </span>
        </div>
      </div>
    </div>
  );
}
