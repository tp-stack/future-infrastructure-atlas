import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset } from "./types";
import InfrastructureCanvasOverlay from "./InfrastructureCanvasOverlay";
import type { CanvasDiagnostics } from "./InfrastructureCanvasOverlay";
import { buildPowerPlantGeoJSON, buildDataCenterGeoJSON, buildCableGeoJSON } from "./geojson";
import { getLightTopoStyle } from "./basemaps";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS } from "./layers";
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
  graticuleVisible?: boolean;
  onHoveredAsset?: (id: string | null) => void;
  onSelectedAsset?: (id: string | null) => void;
  selectedAssetId?: string | null;
  canvasEnabled?: boolean;
}

const CLUSTER_LAYERS = ["power-clusters", "power-cluster-count", "power-points", "data-center-points", "submarine-cable-lines"];

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
  showTestPoints, graticuleVisible,
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
  const [mapStatus, setMapStatus] = useState({
    loaded: false,
    layersReady: false,
    error: null as string | null,
  });

  dataRef.current = data;
  filtersRef.current = filters;
  visibleLayersRef.current = visibleLayers;

  const setMapError = useCallback((message: string) => {
    setMapStatus((prev) => ({ ...prev, error: prev.error || message }));
  }, []);

  const addMapLayers = useCallback(() => {
    const m = map.current;
    if (!m || layersAddedRef.current) return;

    try {
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
          "line-color": CABLE_COLOR,
          "line-width": 2,
          "line-opacity": 0.85,
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
          "circle-stroke-color": "#ffffff",
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
          "text-color": "#ffffff",
          "text-halo-color": "rgba(43,32,8,0.7)",
          "text-halo-width": 1.2,
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
            "Hydro", FUEL_COLORS["Hydro"],
            "Solar", FUEL_COLORS["Solar"],
            "Wind", FUEL_COLORS["Wind"],
            "Natural Gas", FUEL_COLORS["Natural Gas"],
            "Nuclear", FUEL_COLORS["Nuclear"],
            "Coal", FUEL_COLORS["Coal"],
            "Oil", FUEL_COLORS["Oil"],
            "Biomass", FUEL_COLORS["Biomass"],
            "Geothermal", FUEL_COLORS["Geothermal"],
            "Waste", FUEL_COLORS["Waste"],
            "Cogeneration", FUEL_COLORS["Cogeneration"],
            "Wave and Tidal", FUEL_COLORS["Wave and Tidal"],
            FUEL_COLORS["Other"],
          ],
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, 1.5,
            5, 3,
            10, 6,
          ],
          "circle-opacity": 0.85,
          "circle-stroke-color": "rgba(255,255,255,0.75)",
          "circle-stroke-width": 0.7,
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
          "circle-color": DATA_CENTER_COLOR,
          "circle-opacity": 0.9,
          "circle-stroke-color": DATA_CENTER_STROKE_COLOR,
          "circle-stroke-width": 1.5,
        },
      });

      layersAddedRef.current = true;
      setMapStatus((prev) => ({ ...prev, layersReady: true, error: null }));
    } catch (error) {
      setMapError(error instanceof Error ? error.message : String(error));
    }
  }, [data, filters, setMapError]);

  const updateMapSources = useCallback(() => {
    const m = map.current;
    if (!m || !layersAddedRef.current) return;

    const ppGeoJSON = buildPowerPlantGeoJSON(data, filters);
    const dcGeoJSON = buildDataCenterGeoJSON(data, filters);
    const cableGeoJSON = buildCableGeoJSON(data);

    try {
      (m.getSource("power-plants-source") as maplibregl.GeoJSONSource)?.setData(ppGeoJSON);
    } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
    try {
      (m.getSource("data-centers-source") as maplibregl.GeoJSONSource)?.setData(dcGeoJSON);
    } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
    try {
      (m.getSource("submarine-cables-source") as maplibregl.GeoJSONSource)?.setData(cableGeoJSON);
    } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
  }, [data, filters, setMapError]);

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
    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: getLightTopoStyle(),
      center: [10, 30],
      zoom: 1.8,
      renderWorldCopies: false,
      maxBounds: [[-180, -85], [180, 85]],
    });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
    m.on("error", (event) => {
      const message = event.error?.message || "MapLibre reported a render error";
      setMapError(message);
    });
    map.current = m;
    setMapInstance(m);
  }, [setMapError]);

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
      setMapStatus((prev) => ({ ...prev, loaded: true }));
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
      if (!m.getLayer(id)) return;
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

      const interactiveLayers = CLUSTER_LAYERS.filter((id) => m.getLayer(id));
      const features = interactiveLayers.length > 0 ? m.queryRenderedFeatures(e.point, { layers: interactiveLayers }) : [];
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
        }).catch((error: Error) => setMapError(error.message));
        return;
      }

      if (layerId === "power-points") {
        const p = feat.properties as Record<string, unknown>;
        const asset = getPowerPlantFromProps(p);
        const id = `pp-${p._idx ?? `${p.name}-${p.lat}-${p.lon}`}`;
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
      const interactiveLayers = CLUSTER_LAYERS.filter((id) => m.getLayer(id));
      const features = interactiveLayers.length > 0 ? m.queryRenderedFeatures(e.point, { layers: interactiveLayers }) : [];
      const hasFeatures = features && features.length > 0;
      m.getCanvas().style.cursor = hasFeatures ? "pointer" : "";
      if (hasFeatures) {
        const feat = features![0];
        const layerId = feat.layer?.id;
        const props = feat.properties as Record<string, unknown>;
        let hoverId: string | null = null;
        if (layerId === "power-points") {
          hoverId = `pp-${props._idx ?? `${props.name}-${props.lat}-${props.lon}`}`;
        } else if (layerId === "data-center-points") {
          hoverId = `dc-${props.name}-${props.lat}-${props.lon}`;
        } else if (layerId === "submarine-cable-lines") {
          hoverId = `cable-${props.name}`;
        }
        onHoveredAsset?.(hoverId);
      } else {
        onHoveredAsset?.(null);
      }
    };

    const handleMouseLeave = () => {
      m.getCanvas().style.cursor = "";
      onHoveredAsset?.(null);
    };

    m.on("click", handleClick);
    m.on("mousemove", handleMouseMove);
    m.on("mouseleave", handleMouseLeave);

    return () => {
      m.off("click", handleClick);
      m.off("mousemove", handleMouseMove);
      m.off("mouseleave", handleMouseLeave);
    };
  }, [onPopup, onSelectedAsset, onHoveredAsset, setMapError]);

  const handleCanvasDiagnostics = useCallback((d: CanvasDiagnostics) => {
    onCanvasDiagnostics?.(d);
    if (d.active && d.powerPlantsDrawn === 0 && d.recordsReceived > 1000 && !autoResetDoneRef.current && !userInteractedRef.current) {
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
        enabled={Boolean(canvasEnabled)}
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
      {!mapStatus.layersReady && !mapStatus.error && (
        <div className="map-status map-status-loading">
          {mapStatus.loaded ? "Preparing infrastructure layers..." : "Loading map renderer..."}
        </div>
      )}
      {mapStatus.error && (
        <div className="map-status map-status-error">
          <strong>Map renderer issue</strong>
          <span>{mapStatus.error}</span>
        </div>
      )}
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
