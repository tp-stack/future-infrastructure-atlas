import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset } from "./types";
import InfrastructureCanvasOverlay from "./InfrastructureCanvasOverlay";
import type { CanvasDiagnostics } from "./InfrastructureCanvasOverlay";
import { registerPMTilesProtocol, getPMTilesStyle, type TileStatus } from "./pmtiles";
import { findNearest, buildPickIndex, type PickIndex } from "./interaction";
import {
  getValidAssetCoordinates,
  computeLonLatBounds,
  expandBounds,
  getDefaultGlobalBounds,
  boundsToFitBounds,
  isZoomPathological,
  describeZoomLevel,
} from "./viewport";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  onPopup: (asset: Asset | null) => void;
  onCanvasDiagnostics?: (d: CanvasDiagnostics) => void;
  showTestPoints?: boolean;
  tileStatus?: TileStatus;
  graticuleVisible?: boolean;
  onHoveredAsset?: (id: string | null) => void;
  onSelectedAsset?: (id: string | null) => void;
  selectedAssetId?: string | null;
}

const DARK_BG = "#050609";

const CARTO_DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  name: "Dark Atlas",
  sources: {
    "basemap-dark": {
      type: "raster",
      tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"],
      tileSize: 256,
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    },
  },
  layers: [
    { id: "background", type: "background" as const, paint: { "background-color": DARK_BG } },
    { id: "basemap-dark-layer", type: "raster" as const, source: "basemap-dark", minzoom: 0, maxzoom: 20 },
  ],
};

export default function AtlasMap({
  data, filters, visibleLayers, onPopup, onCanvasDiagnostics,
  showTestPoints, tileStatus, graticuleVisible,
  onHoveredAsset, onSelectedAsset, selectedAssetId,
}: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);
  const pickIndexRef = useRef<PickIndex>({ powerPlants: [], dataCenters: [], cables: [] });
  const dataRef = useRef(data);
  const filtersRef = useRef(filters);
  const visibleLayersRef = useRef(visibleLayers);
  const hoveredIdRef = useRef<string | null>(null);
  const initialFitDoneRef = useRef(false);
  const autoResetDoneRef = useRef(false);
  const userInteractedRef = useRef(false);

  dataRef.current = data;
  filtersRef.current = filters;
  visibleLayersRef.current = visibleLayers;

  const fitToData = useCallback((opts?: { maxZoom?: number; padding?: number }) => {
    const m = map.current;
    if (!m) return;
    const d = dataRef.current;
    const fl = filtersRef.current;
    const vl = visibleLayersRef.current;

    const coords = getValidAssetCoordinates(d, fl, vl);
    if (coords.length > 0) {
      const rawBounds = computeLonLatBounds(coords);
      if (rawBounds) {
        const padded = expandBounds(rawBounds, 5);
        const fb = boundsToFitBounds(padded);
        m.fitBounds(fb, { padding: opts?.padding ?? 60, maxZoom: opts?.maxZoom ?? 2.2 });
        return;
      }
    }
    // Fallback to global
    m.fitBounds(boundsToFitBounds(getDefaultGlobalBounds()), { padding: opts?.padding ?? 20, maxZoom: 2.2 });
  }, []);

  const resetToGlobalView = useCallback(() => {
    const m = map.current;
    if (!m) return;
    m.fitBounds(boundsToFitBounds(getDefaultGlobalBounds()), { padding: 20, maxZoom: 2.2 });
    userInteractedRef.current = false;
  }, []);

  const rebuildPickIndex = useCallback(() => {
    const m = map.current;
    if (!m || !dataRef.current) return;
    const d = dataRef.current;
    const fl = filtersRef.current;
    const vl = visibleLayersRef.current;
    const container = m.getContainer();
    const viewW = container.clientWidth;
    const viewH = container.clientHeight;
    if (viewW < 1 || viewH < 1) return;

    const projectFn = (lon: number, lat: number): [number, number] => {
      const p = m.project([lon, lat]);
      return [p.x, p.y];
    };

    const filteredPP = vl.power_plants
      ? d.power_plants.filter((p) => {
          if (fl.fuelType && p.f !== fl.fuelType) return false;
          if (fl.country && p.c !== fl.country) return false;
          if (fl.minMw > 0 && p.mw < fl.minMw) return false;
          return true;
        })
      : [];

    const filteredDC = vl.data_centers
      ? d.data_centers.filter((dc) => dc.mapped_status === "mapped" && dc.lat != null && dc.lon != null)
      : [];

    const filteredCables = vl.cables
      ? d.cables.filter((c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length >= 2)
      : [];

    pickIndexRef.current = buildPickIndex(filteredPP, filteredDC, filteredCables, projectFn, viewW, viewH);
  }, []);

  const initMap = useCallback(() => {
    if (!mapContainer.current || map.current) return;
    const hasPMTiles = tileStatus && (tileStatus.power_plants === "present" || tileStatus.submarine_cables === "present" || tileStatus.data_centers === "present");
    if (hasPMTiles) {
      registerPMTilesProtocol();
    }
    const style = hasPMTiles ? getPMTilesStyle(tileStatus!, visibleLayers) : CARTO_DARK_STYLE;
    const m = new maplibregl.Map({
      container: mapContainer.current,
      style,
      center: [10, 30],
      zoom: 1.8,
      renderWorldCopies: false,
      maxBounds: [[-180, -85], [180, 85]],
    });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
    map.current = m;
    setMapInstance(m);
  }, [tileStatus, visibleLayers]);

  useEffect(() => {
    initMap();
    return () => {
      map.current?.remove();
      map.current = null;
      setMapInstance(null);
    };
  }, [initMap]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const onMapLoad = () => {
      m.resize();
      if (!initialFitDoneRef.current) {
        initialFitDoneRef.current = true;
        setTimeout(() => fitToData({ maxZoom: 2.2 }), 50);
      }
    };

    if (m.loaded()) {
      onMapLoad();
    } else {
      m.once("load", onMapLoad);
    }
  }, [fitToData]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const handleIdle = () => rebuildPickIndex();
    m.on("idle", handleIdle);
    m.on("moveend", handleIdle);

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      userInteractedRef.current = true;
      const idx = pickIndexRef.current;
      const hit = findNearest(e.point.x, e.point.y, idx, 12);
      if (hit) {
        onPopup(hit.asset as Asset);
        onSelectedAsset?.(hit.id);
      } else {
        onPopup(null);
        onSelectedAsset?.(null);
      }
    };

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const idx = pickIndexRef.current;
      const hit = findNearest(e.point.x, e.point.y, idx, 12);
      const canvas = m.getCanvas();
      if (hit) {
        if (hit.id !== hoveredIdRef.current) {
          hoveredIdRef.current = hit.id;
          onHoveredAsset?.(hit.id);
        }
        canvas.style.cursor = "pointer";
      } else {
        if (hoveredIdRef.current !== null) {
          hoveredIdRef.current = null;
          onHoveredAsset?.(null);
        }
        canvas.style.cursor = "";
      }
    };

    const handleMouseLeave = () => {
      if (hoveredIdRef.current !== null) {
        hoveredIdRef.current = null;
        onHoveredAsset?.(null);
      }
      m.getCanvas().style.cursor = "";
    };

    const handleZoom = () => {
      userInteractedRef.current = true;
    };

    m.on("click", handleClick);
    m.on("mousemove", handleMouseMove);
    m.on("mouseleave", handleMouseLeave);
    m.on("zoomend", handleZoom);

    setTimeout(() => rebuildPickIndex(), 500);

    return () => {
      m.off("idle", handleIdle);
      m.off("moveend", handleIdle);
      m.off("click", handleClick);
      m.off("mousemove", handleMouseMove);
      m.off("mouseleave", handleMouseLeave);
      m.off("zoomend", handleZoom);
    };
  }, [onPopup, onHoveredAsset, onSelectedAsset, rebuildPickIndex]);

  const handleCanvasDiagnostics = useCallback((d: CanvasDiagnostics) => {
    onCanvasDiagnostics?.(d);

    if (
      d.powerPlantsDrawn === 0 &&
      d.recordsReceived > 1000 &&
      !autoResetDoneRef.current &&
      !userInteractedRef.current
    ) {
      const m = map.current;
      if (m) {
        const zoom = m.getZoom();
        if (isZoomPathological(zoom) || zoom < 0) {
          autoResetDoneRef.current = true;
          setTimeout(() => resetToGlobalView(), 50);
        }
      }
    }
  }, [onCanvasDiagnostics, resetToGlobalView]);

  const handleResetView = useCallback(() => {
    resetToGlobalView();
  }, [resetToGlobalView]);

  const handleFitData = useCallback(() => {
    fitToData({ maxZoom: 4 });
  }, [fitToData]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="map-canvas" />
      <InfrastructureCanvasOverlay
        data={data}
        filters={filters}
        visibleLayers={visibleLayers}
        mapInstance={mapInstance}
        showTestPoints={showTestPoints}
        onCanvasDiagnostics={handleCanvasDiagnostics}
        hoveredAssetId={hoveredIdRef.current}
        selectedAssetId={selectedAssetId}
        graticuleVisible={graticuleVisible}
      />
      <div className="map-overlay-controls">
        <button className="map-ctrl-btn" onClick={handleResetView} title="Reset global view">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
        <button className="map-ctrl-btn" onClick={handleFitData} title="Fit to visible data">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        </button>
      </div>
    </div>
  );
}
