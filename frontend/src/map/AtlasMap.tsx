import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset } from "./types";
import InfrastructureCanvasOverlay from "./InfrastructureCanvasOverlay";
import type { CanvasDiagnostics } from "./InfrastructureCanvasOverlay";
import { registerPMTilesProtocol, getPMTilesStyle, type TileStatus } from "./pmtiles";
import { buildPowerPlantGeoJSON, buildDataCenterGeoJSON, buildCableGeoJSON } from "./geojson";
import {
  computeFeatureCollectionBounds,
  expandBounds,
  getDefaultGlobalBounds,
  boundsToFitBounds,
  isZoomPathological,
  type LonLatBounds,
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
  canvasEnabled?: boolean;
}

const DARK_BG = "#050609";
const CLUSTER_LAYERS = ["power-clusters", "power-cluster-count", "power-points", "data-center-points", "submarine-cable-lines"];

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

function getPowerPlantFromProps(p: Record<string, unknown>): Asset {
  return {
    n: (p.name as string) || "",
    f: (p.fuel as string) || "",
    mw: (p.capacity_mw as number) || 0,
    c: (p.country as string) || "",
    lat: (p.lat as number) || 0,
    lon: (p.lon as number) || 0,
  } as Asset;
}

function getDataCenterFromProps(p: Record<string, unknown>): Asset {
  return {
    n: (p.name as string) || "",
    op: (p.operator as string) || "",
    c: (p.country as string) || "",
    city: (p.city as string) || "",
    lat: (p.lat as number) || 0,
    lon: (p.lon as number) || 0,
    coordinate_precision: (p.coordinate_precision as string) || "",
    source_license: (p.source_license as string) || "",
    net_count: (p.net_count as number) || 0,
    ix_count: (p.ix_count as number) || 0,
  } as Asset;
}

function getCableFromProps(p: Record<string, unknown>): Asset {
  return {
    n: (p.name as string) || "",
    source: (p.source as string) || "",
    geometry_precision: (p.geometry_precision as string) || "",
    source_license: (p.source_license as string) || "",
    confidence: (p.confidence as number) || 0,
  } as Asset;
}

export default function AtlasMap({
  data, filters, visibleLayers, onPopup, onCanvasDiagnostics,
  showTestPoints, tileStatus, graticuleVisible,
  onHoveredAsset, onSelectedAsset, selectedAssetId,
  canvasEnabled,
}: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);
  const dataRef = useRef(data);
  const filtersRef = useRef(filters);
  const visibleLayersRef = useRef(visibleLayers);
  const initialFitDoneRef = useRef(false);
  const autoResetDoneRef = useRef(false);
  const userInteractedRef = useRef(false);
  const layersAddedRef = useRef(false);

  dataRef.current = data;
  filtersRef.current = filters;
  visibleLayersRef.current = visibleLayers;

  const addMapLayers = useCallback(() => {
    const m = map.current;
    if (!m || layersAddedRef.current) return;

    const ppGeoJSON = buildPowerPlantGeoJSON(data, filters);
    const dcGeoJSON = buildDataCenterGeoJSON(data, filters);
    const cableGeoJSON = buildCableGeoJSON(data);

    m.addSource("power-plants-source", {
      type: "geojson",
      data: ppGeoJSON,
      cluster: true,
      clusterMaxZoom: 7,
      clusterRadius: 35,
    });

    m.addSource("data-centers-source", {
      type: "geojson",
      data: dcGeoJSON,
    });

    m.addSource("submarine-cables-source", {
      type: "geojson",
      data: cableGeoJSON,
    });

    m.addLayer({
      id: "submarine-cable-lines",
      type: "line",
      source: "submarine-cables-source",
      paint: {
        "line-color": "#4cc9e8",
        "line-width": 2,
        "line-opacity": 0.75,
      },
    });

    m.addLayer({
      id: "power-clusters",
      type: "circle",
      source: "power-plants-source",
      filter: ["has", "point_count"],
      paint: {
        "circle-color": ["step", ["get", "point_count"], "#d69a13", 10, "#b8850a", 100, "#8a6508"],
        "circle-radius": ["step", ["get", "point_count"], 18, 10, 24, 100, 32],
        "circle-opacity": 0.85,
        "circle-stroke-color": "#f4efe6",
        "circle-stroke-width": 1.5,
      },
    });

    m.addLayer({
      id: "power-cluster-count",
      type: "symbol",
      source: "power-plants-source",
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count_abbreviated"],
        "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
        "text-size": 11,
      },
      paint: {
        "text-color": "#f4efe6",
        "text-halo-color": "rgba(0,0,0,0.5)",
        "text-halo-width": 1,
      },
    });

    m.addLayer({
      id: "power-points",
      type: "circle",
      source: "power-plants-source",
      filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-color": [
          "match", ["get", "fuel"],
          "Hydro", "#4cc9f0",
          "Solar", "#f2b705",
          "Wind", "#62c370",
          "Natural Gas", "#d99a6c",
          "Nuclear", "#b985d6",
          "Coal", "#d95c5c",
          "Oil", "#c97955",
          "Biomass", "#7ab87a",
          "Geothermal", "#d48a6a",
          "Waste", "#8a8a8a",
          "Cogeneration", "#6a9fd4",
          "Wave and Tidal", "#4dd0e1",
          "#9ca3af",
        ],
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"],
          0, 1.5,
          5, 3,
          10, 6,
        ],
        "circle-opacity": 0.85,
        "circle-stroke-color": "rgba(255,255,255,0.3)",
        "circle-stroke-width": 0.5,
      },
    });

    m.addLayer({
      id: "data-center-points",
      type: "circle",
      source: "data-centers-source",
      paint: {
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"],
          0, 4,
          5, 6,
          10, 8,
        ],
        "circle-color": "#e8e5dc",
        "circle-opacity": 0.9,
        "circle-stroke-color": "#4cc9e8",
        "circle-stroke-width": 1.5,
      },
    });

    layersAddedRef.current = true;
  }, [data, filters]);

  const updateMapSources = useCallback(() => {
    const m = map.current;
    if (!m || !layersAddedRef.current) return;

    const ppGeoJSON = buildPowerPlantGeoJSON(data, filters);
    const dcGeoJSON = buildDataCenterGeoJSON(data, filters);
    const cableGeoJSON = buildCableGeoJSON(data);

    try {
      (m.getSource("power-plants-source") as maplibregl.GeoJSONSource)?.setData(ppGeoJSON);
    } catch { /* source may not exist yet */ }
    try {
      (m.getSource("data-centers-source") as maplibregl.GeoJSONSource)?.setData(dcGeoJSON);
    } catch { /* */ }
    try {
      (m.getSource("submarine-cables-source") as maplibregl.GeoJSONSource)?.setData(cableGeoJSON);
    } catch { /* */ }
  }, [data, filters]);

  const fitToData = useCallback((opts?: { maxZoom?: number; padding?: number }) => {
    const m = map.current;
    if (!m) return;

    const ppFC = buildPowerPlantGeoJSON(dataRef.current, filtersRef.current);
    const dcFC = buildDataCenterGeoJSON(dataRef.current, filtersRef.current);
    const cableFC = buildCableGeoJSON(dataRef.current);

    const ppBounds = computeFeatureCollectionBounds(ppFC);
    const dcBounds = computeFeatureCollectionBounds(dcFC);
    const cableBounds = computeFeatureCollectionBounds(cableFC);

    const allBounds = [ppBounds, dcBounds, cableBounds].filter(Boolean) as LonLatBounds[];
    if (allBounds.length > 0) {
      const merged: LonLatBounds = {
        minLon: Math.min(...allBounds.map((b) => b.minLon)),
        minLat: Math.min(...allBounds.map((b) => b.minLat)),
        maxLon: Math.max(...allBounds.map((b) => b.maxLon)),
        maxLat: Math.max(...allBounds.map((b) => b.maxLat)),
      };
      const padded = expandBounds(merged, 5);
      m.fitBounds(boundsToFitBounds(padded), { padding: opts?.padding ?? 60, maxZoom: opts?.maxZoom ?? 2.5 });
    } else {
      m.fitBounds(boundsToFitBounds(getDefaultGlobalBounds()), { padding: 20, maxZoom: 2.5 });
    }
  }, []);

  const resetToGlobalView = useCallback(() => {
    const m = map.current;
    if (!m) return;
    m.fitBounds(boundsToFitBounds(getDefaultGlobalBounds()), { padding: 20, maxZoom: 2.5 });
    userInteractedRef.current = false;
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
      layersAddedRef.current = false;
    };
  }, [initMap]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const onLoad = () => {
      m.resize();
      addMapLayers();
      if (!initialFitDoneRef.current) {
        initialFitDoneRef.current = true;
        setTimeout(() => fitToData(), 100);
      }
    };

    if (m.loaded()) {
      onLoad();
    } else {
      m.once("load", onLoad);
    }
  }, [addMapLayers, fitToData]);

  useEffect(() => {
    if (!map.current || !layersAddedRef.current) return;
    updateMapSources();
  }, [updateMapSources]);

  useEffect(() => {
    const m = map.current;
    if (!m || !layersAddedRef.current) return;

    const setVis = (id: string, key: string) => {
      m.setLayoutProperty(id, "visibility", visibleLayers[key] ? "visible" : "none");
    };

    setVis("power-clusters", "power_plants");
    setVis("power-cluster-count", "power_plants");
    setVis("power-points", "power_plants");
    setVis("data-center-points", "data_centers");
    setVis("submarine-cable-lines", "cables");
  }, [visibleLayers]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const handleClick = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      userInteractedRef.current = true;
      const canvas = m.getCanvas();

      const features = m.queryRenderedFeatures(e.point, { layers: CLUSTER_LAYERS });
      if (!features || features.length === 0) {
        onPopup(null);
        onSelectedAsset?.(null);
        return;
      }

      const feat = features[0];
      const layerId = feat.layer?.id;

      if (layerId === "power-clusters") {
        const clusterId = feat.properties?.cluster_id;
        const source = m.getSource("power-plants-source") as maplibregl.GeoJSONSource;
        source.getClusterExpansionZoom(clusterId).then((zoom: number) => {
          const geom = feat.geometry as GeoJSON.Point;
          m.easeTo({ center: [geom.coordinates[0], geom.coordinates[1]], zoom: Math.min(zoom + 1, 14) });
        });
        return;
      }

      if (layerId === "power-points") {
        const p = feat.properties as Record<string, unknown>;
        const asset = getPowerPlantFromProps(p);
        const id = `pp-${p.name}-${p.lat}-${p.lon}`;
        onPopup(asset);
        onSelectedAsset?.(id);
        return;
      }

      if (layerId === "data-center-points") {
        const p = feat.properties as Record<string, unknown>;
        const asset = getDataCenterFromProps(p);
        const id = `dc-${p.name}-${p.lat}-${p.lon}`;
        onPopup(asset);
        onSelectedAsset?.(id);
        return;
      }

      if (layerId === "submarine-cable-lines") {
        const p = feat.properties as Record<string, unknown>;
        const asset = getCableFromProps(p);
        const id = `cable-${p.name}`;
        onPopup(asset);
        onSelectedAsset?.(id);
      }
    };

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = m.queryRenderedFeatures(e.point, { layers: CLUSTER_LAYERS });
      const canvas = m.getCanvas();
      if (features && features.length > 0) {
        canvas.style.cursor = "pointer";
      } else {
        canvas.style.cursor = "";
      }
    };

    const handleMouseLeave = () => {
      m.getCanvas().style.cursor = "";
    };

    m.on("click", handleClick);
    m.on("mousemove", handleMouseMove);
    m.on("mouseleave", handleMouseLeave);

    return () => {
      m.off("click", handleClick);
      m.off("mousemove", handleMouseMove);
      m.off("mouseleave", handleMouseLeave);
    };
  }, [onPopup, onSelectedAsset]);

  const handleCanvasDiagnostics = useCallback((d: CanvasDiagnostics) => {
    onCanvasDiagnostics?.(d);
    if (d.powerPlantsDrawn === 0 && d.recordsReceived > 1000 && !autoResetDoneRef.current && !userInteractedRef.current) {
      const m = map.current;
      if (m && (isZoomPathological(m.getZoom()) || m.getZoom() < 0)) {
        autoResetDoneRef.current = true;
        setTimeout(() => resetToGlobalView(), 50);
      }
    }
  }, [onCanvasDiagnostics, resetToGlobalView]);

  const handleResetView = useCallback(() => resetToGlobalView(), [resetToGlobalView]);
  const handleFitData = useCallback(() => fitToData({ maxZoom: 4 }), [fitToData]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="map-canvas" />
      <InfrastructureCanvasOverlay
        data={data}
        filters={filters}
        visibleLayers={visibleLayers}
        mapInstance={canvasEnabled ? mapInstance : null}
        showTestPoints={showTestPoints}
        onCanvasDiagnostics={handleCanvasDiagnostics}
        hoveredAssetId={null}
        selectedAssetId={selectedAssetId}
        graticuleVisible={canvasEnabled ? graticuleVisible : false}
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
