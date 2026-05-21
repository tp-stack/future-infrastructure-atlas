import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset, AtlasCore } from "./types";
import InfrastructureCanvasOverlay from "./InfrastructureCanvasOverlay";
import type { CanvasDiagnostics } from "./InfrastructureCanvasOverlay";
import { buildPowerPlantGeoJSON, buildDataCenterGeoJSON, buildCableGeoJSON } from "./geojson";
import { getLightTopoStyle } from "./basemaps";
import { CABLE_COLOR, CABLE_HOVER_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, POWER_LINE_DEFAULT_COLOR, POWER_LINE_HVDC_COLOR, SUBSTATION_COLOR, SUBSTATION_STROKE_COLOR } from "./layers";
import { buildFuelCircleColorExpression } from "./fuelMatch";
import { registerPMTilesProtocol, getPMTilesSources, getPMTilesLayers, type TileStatus } from "./pmtiles";
import { useDebounce } from "../utils/debounce";
import {
  computeFeatureCollectionBounds,
  expandBounds,
  getDefaultGlobalBounds,
  boundsToFitBounds,
  isZoomPathological,
  FIT_WORLD_MIN_LON,
  FIT_WORLD_MAX_LON,
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
  core?: AtlasCore;
  navigateTo?: { lon: number; lat: number; zoom?: number } | null;
  layerOpacity?: Record<string, number>;
  powerLinesData?: GeoJSON.FeatureCollection | null;
  substationsData?: GeoJSON.FeatureCollection | null;
}

const GEOJSON_CLUSTER_LAYERS = ["power-clusters", "power-cluster-count", "power-points", "data-center-points", "submarine-cable-lines", "power-line-lines", "substation-points"];
const PMTILES_CLUSTER_LAYERS = ["power_plants_tiles-layer", "data_centers_tiles-layer", "submarine_cables_tiles-layer", "power_lines_tiles-layer", "substations_tiles-layer"];

function getTileStatusFromCore(core: AtlasCore): TileStatus {
  const reg = core.tile_registry || {};
  return {
    power_plants: reg.power_plants?.status?.startsWith("present") ? "present" : "missing",
    submarine_cables: reg.submarine_cables?.status?.startsWith("present") ? "present" : "missing",
    data_centers: reg.data_centers?.status?.startsWith("present") ? "present" : "missing",
    power_lines: reg.power_lines?.status?.startsWith("present") ? "present" : "missing",
    substations: reg.substations?.status?.startsWith("present") ? "present" : "missing",
  };
}

function isPowerLineTileError(event: unknown): boolean {
  const raw = event as unknown as { sourceId?: string; error?: { message?: string } };
  const sourceId = raw.sourceId || "";
  const message = raw.error?.message || "";
  return (
    sourceId === "power_lines_tiles" ||
    message.includes("power_lines") ||
    message.includes("power-lines") ||
    message.includes("power_lines.pmtiles")
  );
}

function or(a: unknown, b: unknown): unknown { return a || b; }

function str(v: unknown): string { return v != null ? String(v) : ""; }
function num(v: unknown, d: number = 0): number { const n = typeof v === "number" ? v : parseFloat(String(v ?? "")); return Number.isFinite(n) ? n : d; }
function bool(v: unknown): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  const s = String(v ?? "").toLowerCase();
  return s === "true" || s === "t" || s === "1" || s === "yes";
}

function getPowerPlantFromProps(p: Record<string, unknown>): Asset {
  return {
    kind: "power_plant",
    n: str(or(p.name, p.n)),
    f: str(or(p.fuel, p.f)),
    mw: num(or(p.capacity_mw, p.mw)),
    c: str(or(p.country, p.c)),
    lat: num(or(p.lat, 0)),
    lon: num(or(p.lon, 0)),
  } as Asset;
}

function getDataCenterFromProps(p: Record<string, unknown>): Asset {
  return {
    kind: "data_center",
    n: str(or(p.name, p.n)),
    op: str(or(p.operator, p.op)),
    c: str(or(p.country, p.c)),
    city: str(p.city),
    lat: num(or(p.lat, 0)),
    lon: num(or(p.lon, 0)),
    coordinate_precision: str(p.coordinate_precision),
    source_license: str(p.source_license),
    net_count: num(p.net_count),
    ix_count: num(p.ix_count),
  } as Asset;
}

function getCableFromProps(p: Record<string, unknown>): Asset {
  return {
    kind: "submarine_cable",
    n: str(or(p.name, p.n)),
    source: str(p.source),
    geometry_precision: str(p.geometry_precision),
    source_license: str(p.source_license),
    confidence: num(p.confidence),
  } as Asset;
}

function getPowerLineFromProps(p: Record<string, unknown>): Asset {
  const name = str(or(p.n, p.id)) || "Power line";
  return {
    kind: "power_line",
    id: str(p.id),
    n: name,
    voltage: num(p.voltage),
    circuits: num(p.circuits),
    cables: num(p.cables),
    length_km: num(p.length_km),
    underground: bool(p.underground),
    country: str(or(p.country, p.c)),
    type: str(p.type),
    s_nom_mva: num(p.s_nom_mva),
  } as Asset;
}

function getSubstationFromProps(p: Record<string, unknown>): Asset {
  const name = str(or(p.n, p.id)) || "Substation";
  return {
    kind: "substation",
    id: str(p.id),
    n: name,
    voltage: num(p.voltage),
    dc: bool(p.dc),
    symbol: str(p.symbol),
    under_construction: bool(p.under_construction),
    country: str(or(p.country, p.c)),
    lat: num(or(p.lat, 0)),
    lon: num(or(p.lon, 0)),
  } as Asset;
}

function powerLineColorExpression(): maplibregl.ExpressionSpecification {
  return [
    "case",
    ["==", ["get", "type"], "HVDC"],
    POWER_LINE_HVDC_COLOR,
    [">=", ["coalesce", ["get", "voltage"], 0], 380],
    "#d45050",
    [">=", ["coalesce", ["get", "voltage"], 0], 220],
    "#d69a13",
    [">=", ["coalesce", ["get", "voltage"], 0], 110],
    "#2f6b4f",
    [">=", ["coalesce", ["get", "voltage"], 0], 45],
    "#087ea4",
    [">", ["coalesce", ["get", "voltage"], 0], 0],
    "#8d93a1",
    POWER_LINE_DEFAULT_COLOR,
  ] as maplibregl.ExpressionSpecification;
}

function boundsFromCore(core?: AtlasCore): LonLatBounds | null {
  const raw = core?.bounds?.power_lines;
  if (!raw || typeof raw !== "object") return null;
  const b = raw as Record<string, unknown>;
  const minLon = num(b.minLon);
  const minLat = num(b.minLat);
  const maxLon = num(b.maxLon);
  const maxLat = num(b.maxLat);
  if (![minLon, minLat, maxLon, maxLat].every(Number.isFinite)) return null;
  if (minLon >= maxLon || minLat >= maxLat) return null;
  return { minLon, minLat, maxLon, maxLat };
}

function addPowerPlantLayers(m: maplibregl.Map, beforeId?: string) {
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
  }, beforeId);

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
  }, beforeId);

  m.addLayer({
    id: "power-points",
    type: "circle",
    source: "power-plants-source",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": buildFuelCircleColorExpression(),
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
  }, beforeId);
}

function addPowerLineLayer(m: maplibregl.Map, beforeId?: string) {
  m.addLayer({
    id: "power-line-lines",
    type: "line",
    source: "power-lines-source",
    paint: {
      "line-color": powerLineColorExpression(),
      "line-width": [
        "interpolate", ["linear"], ["zoom"],
        2, 0.6,
        6, 1.2,
        10, 2.5,
      ],
      "line-opacity": 0.7,
    },
  }, beforeId);
}

function addSubstationLayer(m: maplibregl.Map, beforeId?: string) {
  m.addLayer({
    id: "substation-points",
    type: "circle",
    source: "substations-source",
    paint: {
      "circle-radius": [
        "interpolate", ["linear"], ["zoom"],
        2, 2,
        6, 4,
        10, 7,
      ],
      "circle-color": SUBSTATION_COLOR,
      "circle-opacity": 0.85,
      "circle-stroke-color": SUBSTATION_STROKE_COLOR,
      "circle-stroke-width": 1,
    },
  }, beforeId);
}

export default function AtlasMap({
  data, filters, visibleLayers, onPopup, onCanvasDiagnostics,
  showTestPoints, graticuleVisible,
  onHoveredAsset, onSelectedAsset, selectedAssetId,
  canvasEnabled, core, navigateTo, layerOpacity,
  powerLinesData,
  substationsData,
}: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);
  const initialFitDoneRef = useRef(false);
  const autoResetDoneRef = useRef(false);
  const userInteractedRef = useRef(false);
  const layersAddedRef = useRef(false);
  const cleanupFnsRef = useRef<Array<() => void>>([]);
  const [mapStatus, setMapStatus] = useState({
    loaded: false,
    layersReady: false,
    error: null as string | null,
  });

  const tileStatus = core ? getTileStatusFromCore(core) : null;
  const usePMTiles = tileStatus !== null && Object.values(tileStatus).some((status) => status === "present");
  const clusterLayers = usePMTiles ? PMTILES_CLUSTER_LAYERS : GEOJSON_CLUSTER_LAYERS;
  const prevCableHover = useRef<string | null>(null);

  const setMapError = useCallback((message: string) => {
    setMapStatus((prev) => ({ ...prev, error: prev.error || message }));
  }, []);

  const doUpdateSources = useCallback(() => {
    const m = map.current;
    if (!m || !layersAddedRef.current) return;

    if (!usePMTiles) {
      try {
        (m.getSource("power-plants-source") as maplibregl.GeoJSONSource)?.setData(buildPowerPlantGeoJSON(data, filters));
      } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
      try {
        (m.getSource("data-centers-source") as maplibregl.GeoJSONSource)?.setData(buildDataCenterGeoJSON(data, filters));
      } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
      try {
        (m.getSource("submarine-cables-source") as maplibregl.GeoJSONSource)?.setData(buildCableGeoJSON(data));
      } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
    }
    if (powerLinesData) {
      try {
        if (!m.getSource("power-lines-source") && (!usePMTiles || tileStatus?.power_lines !== "present")) {
          m.addSource("power-lines-source", { type: "geojson", data: powerLinesData });
          addPowerLineLayer(m);
        }
        (m.getSource("power-lines-source") as maplibregl.GeoJSONSource)?.setData(powerLinesData);
      } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
    }
    if (substationsData) {
      try {
        if (!m.getSource("substations-source") && (!usePMTiles || tileStatus?.substations !== "present")) {
          m.addSource("substations-source", { type: "geojson", data: substationsData });
          addSubstationLayer(m);
        }
        (m.getSource("substations-source") as maplibregl.GeoJSONSource)?.setData(substationsData);
      } catch (error) { setMapError(error instanceof Error ? error.message : String(error)); }
    }
  }, [data, filters, setMapError, usePMTiles, tileStatus, powerLinesData, substationsData]);

  const { call: debouncedUpdateSources, cancel: cancelUpdate } = useDebounce(doUpdateSources, 300);

  const addMapLayers = useCallback(() => {
    const m = map.current;
    if (!m || layersAddedRef.current) return;

    try {
      if (usePMTiles && tileStatus) {
        registerPMTilesProtocol();
        const tileSources = getPMTilesSources(tileStatus, core?.tile_registry);
        for (const [id, spec] of Object.entries(tileSources)) {
          m.addSource(id, spec);
        }
        const tileLayers = getPMTilesLayers(tileStatus, { power_plants: true, cables: true, data_centers: true, power_lines: true, substations: true });
        for (const layer of tileLayers) {
          m.addLayer(layer);
        }
        if (tileStatus.power_lines !== "present" && powerLinesData) {
          m.addSource("power-lines-source", { type: "geojson", data: powerLinesData });
          addPowerLineLayer(m);
        }
        if (tileStatus.substations !== "present" && substationsData) {
          m.addSource("substations-source", { type: "geojson", data: substationsData });
          addSubstationLayer(m);
        }
      } else {
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
            "line-color": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              CABLE_HOVER_COLOR,
              CABLE_COLOR,
            ],
            "line-width": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              4,
              2.5,
            ],
            "line-opacity": [
              "case",
              ["boolean", ["feature-state", "hover"], false],
              1,
              0.85,
            ],
          },
        });

        addPowerPlantLayers(m);

        m.addLayer({
          id: "power-heatmap",
          type: "heatmap",
          source: "power-plants-source",
          paint: {
            "heatmap-weight": 1,
            "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 3, 10, 5],
            "heatmap-color": [
              "interpolate", ["linear"], ["heatmap-density"],
              0, "rgba(214,154,19,0)",
              0.2, "rgba(214,154,19,0.3)",
              0.4, "#d69a13",
              0.6, "#e8b02a",
              0.8, "#f4d03f",
              1, "#fef9e7",
            ],
            "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 0, 10, 5, 20, 10, 40],
            "heatmap-opacity": 0.75,
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

        if (powerLinesData) {
          m.addSource("power-lines-source", { type: "geojson", data: powerLinesData });
          addPowerLineLayer(m);
        }

        if (substationsData) {
          m.addSource("substations-source", { type: "geojson", data: substationsData });
          addSubstationLayer(m);
        }
      }

      layersAddedRef.current = true;
      setMapStatus((prev) => ({ ...prev, layersReady: true, error: null }));
    } catch (error) {
      setMapError(error instanceof Error ? error.message : String(error));
    }
  }, [core, data, filters, setMapError, usePMTiles, tileStatus, powerLinesData, substationsData]);

  const fitToData = useCallback((opts?: { maxZoom?: number; padding?: number }) => {
    const m = map.current;
    if (!m) return;

    const ppFC = buildPowerPlantGeoJSON(data, filters);
    const dcFC = buildDataCenterGeoJSON(data, filters);
    const cableFC = buildCableGeoJSON(data);
    const lineFC = powerLinesData;
    const substationFC = substationsData;

    const ppBounds = computeFeatureCollectionBounds(ppFC);
    const dcBounds = computeFeatureCollectionBounds(dcFC);
    const cableBounds = computeFeatureCollectionBounds(cableFC);
    const lineBounds = lineFC ? computeFeatureCollectionBounds(lineFC) : boundsFromCore(core);
    const substationBounds = substationFC ? computeFeatureCollectionBounds(substationFC) : null;

    const allBounds = [ppBounds, dcBounds, cableBounds, lineBounds, substationBounds].filter(Boolean) as LonLatBounds[];
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
  }, [core, data, filters, powerLinesData, substationsData]);

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
      preserveDrawingBuffer: true,
      maxBounds: [[FIT_WORLD_MIN_LON, -85], [FIT_WORLD_MAX_LON, 85]],
    });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
    m.on("error", (event) => {
      if (isPowerLineTileError(event)) {
        setMapError("Power-line PMTiles failed to load. Check CORS, Range requests, or tile URL.");
        return;
      }
      const message = event.error?.message || "MapLibre reported a render error";
      setMapError(message);
    });
    map.current = m;
    (window as unknown as { __atlasMap?: maplibregl.Map }).__atlasMap = m;
    setMapInstance(m);
  }, [setMapError]);

  useEffect(() => {
    initMap();
    return () => {
      cancelUpdate();
      for (const fn of cleanupFnsRef.current) fn();
      cleanupFnsRef.current = [];
      map.current?.remove();
      delete (window as unknown as { __atlasMap?: maplibregl.Map }).__atlasMap;
      map.current = null;
      setMapInstance(null);
      layersAddedRef.current = false;
    };
  }, [initMap, cancelUpdate]);

  useEffect(() => {
    if (!map.current || !navigateTo) return;
    map.current.flyTo({ center: [navigateTo.lon, navigateTo.lat], zoom: navigateTo.zoom ?? 5, duration: 1500 });
  }, [navigateTo]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const onLoad = () => {
      m.resize();
      setMapStatus((prev) => ({ ...prev, loaded: true }));
      addMapLayers();
      if (!initialFitDoneRef.current) {
        initialFitDoneRef.current = true;
        fitToData();
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
    debouncedUpdateSources();
  }, [debouncedUpdateSources]);

  useEffect(() => {
    const m = map.current;
    if (!m || !layersAddedRef.current) return;

    const setVis = (id: string, key: string) => {
      if (!m.getLayer(id)) return;
      m.setLayoutProperty(id, "visibility", visibleLayers[key] ? "visible" : "none");
    };

    if (usePMTiles) {
      setVis("power_plants_tiles-layer", "power_plants");
      setVis("data_centers_tiles-layer", "data_centers");
      setVis("submarine_cables_tiles-layer", "cables");
      setVis("power_lines_tiles-layer", "power_lines");
      setVis("substations_tiles-layer", "substations");
    }
    setVis("power-heatmap", "heatmap");
    setVis("power-clusters", "power_plants");
    setVis("power-cluster-count", "power_plants");
    setVis("power-points", "power_plants");
    setVis("data-center-points", "data_centers");
    setVis("submarine-cable-lines", "cables");
    setVis("power-line-lines", "power_lines");
    setVis("substation-points", "substations");
  }, [visibleLayers]);

  useEffect(() => {
    const m = map.current;
    if (!m || !layersAddedRef.current || !layerOpacity) return;

    const setOpacity = (id: string, key: string) => {
      if (!m.getLayer(id)) return;
      const opacity = layerOpacity[key];
      if (opacity == null) return;
      const type = m.getLayer(id)?.type;
      if (type === "circle") {
        m.setPaintProperty(id, "circle-opacity", opacity);
      } else if (type === "line") {
        m.setPaintProperty(id, "line-opacity", opacity);
      } else if (type === "heatmap") {
        m.setPaintProperty(id, "heatmap-opacity", opacity);
      }
    };

    setOpacity("power-clusters", "power_plants");
    setOpacity("power-points", "power_plants");
    setOpacity("power-heatmap", "heatmap");
    setOpacity("data-center-points", "data_centers");
    setOpacity("submarine-cable-lines", "cables");
    setOpacity("power-line-lines", "power_lines");
    setOpacity("substation-points", "substations");
    setOpacity("power_plants_tiles-layer", "power_plants");
    setOpacity("data_centers_tiles-layer", "data_centers");
    setOpacity("submarine_cables_tiles-layer", "cables");
    setOpacity("power_lines_tiles-layer", "power_lines");
    setOpacity("substations_tiles-layer", "substations");
  }, [layerOpacity]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const handleClick = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      userInteractedRef.current = true;

      const interactiveLayers = clusterLayers.filter((id) => m.getLayer(id));
      const features = interactiveLayers.length > 0 ? m.queryRenderedFeatures(e.point, { layers: interactiveLayers }) : [];
      if (!features || features.length === 0) {
        onPopup(null);
        onSelectedAsset?.(null);
        return;
      }

      const feat = features[0];
      const layerId = feat.layer?.id;

      if (usePMTiles) {
        if (layerId === "power_plants_tiles-layer" || layerId === "data_centers_tiles-layer" || layerId === "submarine_cables_tiles-layer" || layerId === "power_lines_tiles-layer" || layerId === "substations_tiles-layer") {
          const p = feat.properties as Record<string, unknown>;
          let asset: Asset;
          let id: string;
          if (layerId === "power_plants_tiles-layer") {
            asset = getPowerPlantFromProps(p);
            id = `pp-pmtiles-${p.n ?? "?"}`;
          } else if (layerId === "data_centers_tiles-layer") {
            asset = getDataCenterFromProps(p);
            id = `dc-pmtiles-${p.n ?? "?"}`;
          } else if (layerId === "submarine_cables_tiles-layer") {
            asset = getCableFromProps(p);
            id = `cable-pmtiles-${p.n ?? "?"}`;
          } else if (layerId === "power_lines_tiles-layer") {
            asset = getPowerLineFromProps(p);
            id = `power-line-pmtiles-${p.id ?? p.n ?? "?"}`;
          } else {
            asset = getSubstationFromProps(p);
            id = `substation-pmtiles-${p.id ?? p.n ?? "?"}`;
          }
          onPopup(asset);
          onSelectedAsset?.(id);
        }
        if (layerId === "power-line-lines") {
          const p = feat.properties as Record<string, unknown>;
          onPopup(getPowerLineFromProps(p));
          onSelectedAsset?.(`power-line-${p.id ?? "?"}`);
        } else if (layerId === "substation-points") {
          const p = feat.properties as Record<string, unknown>;
          onPopup(getSubstationFromProps(p));
          onSelectedAsset?.(`substation-${p.id ?? p.n ?? "?"}`);
        }
        return;
      }

      if (layerId === "power-clusters") {
        const clusterId = feat.properties?.cluster_id;
        const source = m.getSource("power-plants-source") as maplibregl.GeoJSONSource;
        source.getClusterExpansionZoom(clusterId).then((zoom: number) => {
          const geom = feat.geometry as GeoJSON.Point;
          const [lon, lat] = geom.coordinates;
          if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
          m.easeTo({ center: [lon, lat], zoom: Math.min(zoom + 1, 8) });
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
        return;
      }

      if (layerId === "power-line-lines") {
        const p = feat.properties as Record<string, unknown>;
        const asset = getPowerLineFromProps(p);
        const id = `power-line-${p.id ?? "?"}`;
        onPopup(asset);
        onSelectedAsset?.(id);
        return;
      }

      if (layerId === "substation-points") {
        const p = feat.properties as Record<string, unknown>;
        const asset = getSubstationFromProps(p);
        const id = `substation-${p.id ?? p.n ?? "?"}`;
        onPopup(asset);
        onSelectedAsset?.(id);
      }
    };

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const interactiveLayers = clusterLayers.filter((id) => m.getLayer(id));
      const features = interactiveLayers.length > 0 ? m.queryRenderedFeatures(e.point, { layers: interactiveLayers }) : [];
      const hasFeatures = features && features.length > 0;
      m.getCanvas().style.cursor = hasFeatures ? "pointer" : "";
      if (hasFeatures) {
        if (!usePMTiles && m.getLayer("submarine-cable-lines")) {
          const cableFeat = features.find((f) => f.layer?.id === "submarine-cable-lines");
          const cableId = cableFeat?.id != null ? String(cableFeat.id) : null;
          if (cableId && prevCableHover.current !== cableId) {
            if (prevCableHover.current) {
              try { m.setFeatureState({ source: "submarine-cables-source", id: prevCableHover.current }, { hover: false }); } catch {}
            }
            try { m.setFeatureState({ source: "submarine-cables-source", id: cableId }, { hover: true }); } catch {}
            prevCableHover.current = cableId;
          } else if (!cableId && prevCableHover.current) {
            try { m.setFeatureState({ source: "submarine-cables-source", id: prevCableHover.current }, { hover: false }); } catch {}
            prevCableHover.current = null;
          }
        }
        const feat = features![0];
        const layerId = feat.layer?.id;
        const props = feat.properties as Record<string, unknown>;
        let hoverId: string | null = null;
        if (usePMTiles) {
          if (layerId === "power_plants_tiles-layer") hoverId = `pp-pmtiles-${props.n ?? "?"}`;
          else if (layerId === "data_centers_tiles-layer") hoverId = `dc-pmtiles-${props.n ?? "?"}`;
          else if (layerId === "submarine_cables_tiles-layer") hoverId = `cable-pmtiles-${props.n ?? "?"}`;
          else if (layerId === "power_lines_tiles-layer") hoverId = `power-line-pmtiles-${props.id ?? props.n ?? "?"}`;
          else if (layerId === "substations_tiles-layer") hoverId = `substation-pmtiles-${props.id ?? props.n ?? "?"}`;
          else if (layerId === "power-line-lines") hoverId = `power-line-${props.id ?? "?"}`;
          else if (layerId === "substation-points") hoverId = `substation-${props.id ?? props.n ?? "?"}`;
        } else {
          if (layerId === "power-points") {
            hoverId = `pp-${props._idx ?? `${props.name}-${props.lat}-${props.lon}`}`;
          } else if (layerId === "data-center-points") {
            hoverId = `dc-${props.name}-${props.lat}-${props.lon}`;
          } else if (layerId === "submarine-cable-lines") {
            hoverId = `cable-${props.name}`;
          } else if (layerId === "power-line-lines") {
            hoverId = `power-line-${props.id ?? "?"}`;
          } else if (layerId === "substation-points") {
            hoverId = `substation-${props.id ?? props.n ?? "?"}`;
          }
        }
        onHoveredAsset?.(hoverId);
      } else {
        onHoveredAsset?.(null);
        if (!usePMTiles && prevCableHover.current) {
          try { m.setFeatureState({ source: "submarine-cables-source", id: prevCableHover.current }, { hover: false }); } catch {}
          prevCableHover.current = null;
        }
      }
    };

    const handleMouseLeave = () => {
      m.getCanvas().style.cursor = "";
      onHoveredAsset?.(null);
      if (!usePMTiles && prevCableHover.current) {
        try { m.setFeatureState({ source: "submarine-cables-source", id: prevCableHover.current }, { hover: false }); } catch {}
        prevCableHover.current = null;
      }
    };

    m.on("click", handleClick);
    m.on("mousemove", handleMouseMove);
    m.on("mouseleave", handleMouseLeave);

    return () => {
      m.off("click", handleClick);
      m.off("mousemove", handleMouseMove);
      m.off("mouseleave", handleMouseLeave);
    };
  }, [onPopup, onSelectedAsset, onHoveredAsset, setMapError, clusterLayers, usePMTiles]);

  const handleCanvasDiagnostics = useCallback((d: CanvasDiagnostics) => {
    onCanvasDiagnostics?.(d);
    if (d.active && d.powerPlantsDrawn === 0 && d.recordsReceived > 1000 && !autoResetDoneRef.current && !userInteractedRef.current) {
      const m = map.current;
      if (m && (isZoomPathological(m.getZoom()) || m.getZoom() < 0)) {
        autoResetDoneRef.current = true;
        const t = setTimeout(() => resetToGlobalView(), 50);
        cleanupFnsRef.current.push(() => clearTimeout(t));
      }
    }
  }, [onCanvasDiagnostics, resetToGlobalView]);

  const handleResetView = useCallback(() => resetToGlobalView(), [resetToGlobalView]);
  const handleFitData = useCallback(() => fitToData({ maxZoom: 4 }), [fitToData]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="map-canvas" />
      {canvasEnabled && (
        <InfrastructureCanvasOverlay
          enabled
          data={data}
          filters={filters}
          visibleLayers={visibleLayers}
          mapInstance={mapInstance}
          showTestPoints={showTestPoints}
          onCanvasDiagnostics={handleCanvasDiagnostics}
          hoveredAssetId={null}
          selectedAssetId={selectedAssetId}
          graticuleVisible={graticuleVisible}
        />
      )}
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
