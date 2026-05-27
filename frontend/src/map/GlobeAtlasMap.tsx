import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasCore, AtlasData, Asset, Cable, DataCenter, FilterState, PowerLine, PowerPlant } from "./types";
import type { InteractableType } from "./interaction";
import type { CableCompanyStat, CableFilterState } from "./cables";
import { DEFAULT_CABLE_FILTERS } from "./cables";
import type { LonLatBounds } from "./viewport";
import {
  buildCableGeoJSON,
  buildDataCenterGeoJSON,
  buildGraticuleGeoJSON,
  buildPowerPlantGeoJSON,
  computeCombinedBounds,
  computeFeatureCollectionBounds,
} from "./geojson";
import { getGlobeTopoStyle } from "./basemaps";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS } from "./layers";
import {
  getPMTilesSources,
  getTileStatusFromCore,
  powerCableColorExpression,
  powerLineColorExpression,
  POWER_CABLE_FILTER,
  POWER_OVERHEAD_FILTER,
  registerPMTilesProtocol,
} from "./pmtiles";
import {
  DEFAULT_GRID_CONTINENT_FILTERS,
  buildGridContinentFilter,
  type GridContinentFilters,
} from "./continents";
import type { AtlasTheme } from "../utils/theme";

interface Props {
  data: AtlasData;
  filters?: FilterState;
  visibleLayers?: Record<string, boolean>;
  graticuleVisible?: boolean;
  proof?: boolean;
  onAssetSelect?: (asset: Asset | null, assetType: InteractableType | null) => void;
  cableCompanyStats?: CableCompanyStat[];
  cableFilters?: CableFilterState;
  navigateTo?: { lon: number; lat: number; zoom?: number; bounds?: LonLatBounds } | null;
  core?: AtlasCore;
  powerLinesData?: GeoJSON.FeatureCollection | null;
  layerOpacity?: Record<string, number>;
  gridContinentFilters?: GridContinentFilters;
  theme?: AtlasTheme;
}

const DEFAULT_FILTERS: FilterState = { fuelType: "", country: "", minMw: 0 };
const DEFAULT_VISIBLE_LAYERS = { power_plants: true, cables: true, data_centers: true };
const WORLD_BOUNDS: LonLatBounds = { minLon: -179.5, minLat: -70, maxLon: 179.5, maxLat: 82 };
const INTERACTIVE_LAYERS = [
  "globe-power-points",
  "globe-data-center-points",
  "globe-submarine-cable-lines",
  "globe-power-line-lines",
  "globe-power-line-cables",
  "globe-openinframap-power-line-lines",
  "globe-openinframap-power-line-cables",
  "globe-proof-points",
];

const PROOF_POINTS: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", geometry: { type: "Point", coordinates: [-0.1278, 51.5074] }, properties: { n: "London" } },
    { type: "Feature", geometry: { type: "Point", coordinates: [-74.006, 40.7128] }, properties: { n: "New York" } },
    { type: "Feature", geometry: { type: "Point", coordinates: [103.8198, 1.3521] }, properties: { n: "Singapore" } },
    { type: "Feature", geometry: { type: "Point", coordinates: [139.6503, 35.6762] }, properties: { n: "Tokyo" } },
    { type: "Feature", geometry: { type: "Point", coordinates: [-46.6333, -23.5505] }, properties: { n: "Sao Paulo" } },
  ],
};

function paddedBounds(bounds: LonLatBounds, padDeg = 4): LonLatBounds {
  return {
    minLon: Math.max(-179.5, bounds.minLon - padDeg),
    minLat: Math.max(-85, bounds.minLat - padDeg),
    maxLon: Math.min(179.5, bounds.maxLon + padDeg),
    maxLat: Math.min(85, bounds.maxLat + padDeg),
  };
}

function toFitBounds(bounds: LonLatBounds): [[number, number], [number, number]] {
  return [[bounds.minLon, bounds.minLat], [bounds.maxLon, bounds.maxLat]];
}

function str(v: unknown): string {
  return v != null ? String(v) : "";
}

function num(v: unknown, fallback = 0): number {
  const parsed = typeof v === "number" ? v : parseFloat(String(v ?? ""));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function bool(v: unknown): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  const parsed = String(v ?? "").toLowerCase();
  return parsed === "true" || parsed === "t" || parsed === "1" || parsed === "yes";
}

function mergeBounds(...boundsList: Array<LonLatBounds | null | undefined>): LonLatBounds | null {
  const valid = boundsList.filter(Boolean) as LonLatBounds[];
  if (!valid.length) return null;
  return {
    minLon: Math.min(...valid.map((b) => b.minLon)),
    minLat: Math.min(...valid.map((b) => b.minLat)),
    maxLon: Math.max(...valid.map((b) => b.maxLon)),
    maxLat: Math.max(...valid.map((b) => b.maxLat)),
  };
}

function boundsFromCore(core: AtlasCore | undefined, key: "power_lines" | "openinframap_power_lines"): LonLatBounds | null {
  const raw = core?.bounds?.[key];
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

function featureLngLat(feature: maplibregl.MapGeoJSONFeature, fallback: maplibregl.LngLat): [number, number] {
  if (feature.geometry.type === "Point") {
    const coords = (feature.geometry as GeoJSON.Point).coordinates;
    if (Number.isFinite(coords[0]) && Number.isFinite(coords[1])) return [coords[0], coords[1]];
  }
  return [fallback.lng, fallback.lat];
}

function powerLineFromFeature(props: Record<string, unknown>): PowerLine {
  return {
    kind: "power_line",
    id: str(props.id),
    n: str(props.n || props.name || props.id) || "Power line",
    voltage: num(props.voltage),
    circuits: num(props.circuits),
    cables: num(props.cables),
    length_km: num(props.length_km),
    underground: bool(props.underground),
    country: str(props.country || props.c),
    type: str(props.type),
    s_nom_mva: num(props.s_nom_mva),
  };
}

function cableFromFeature(props: Record<string, unknown>, sourceCable?: Cable): Cable {
  return {
    kind: "submarine_cable",
    n: str(props.n || props.name),
    source: str(props.source),
    geometry: sourceCable?.geometry || [],
    mapped_status: "mapped",
    geometry_precision: str(props.geometry_precision),
    source_license: str(props.source_license),
    confidence: num(props.confidence),
    operators: str(props.operators),
    landing_points: Array.isArray(props.landing_points) ? props.landing_points : str(props.landing_points),
    length_km: str(props.length_km),
  };
}

function assetFromFeature(feature: maplibregl.MapGeoJSONFeature, data: AtlasData): { asset: Asset; type: InteractableType } | null {
  const props = feature.properties as Record<string, unknown>;
  const layerId = feature.layer?.id;

  if (layerId === "globe-power-points") {
    const asset: PowerPlant = {
      kind: "power_plant",
      n: str(props.n || props.name),
      c: str(props.c || props.country),
      f: str(props.f || props.fuel),
      mw: num(props.mw || props.capacity_mw),
      lat: num(props.lat),
      lon: num(props.lon),
      mapped_status: "mapped",
    };
    return { asset, type: "power_plant" };
  }

  if (layerId === "globe-data-center-points") {
    const asset: DataCenter = {
      kind: "data_center",
      n: str(props.n || props.name),
      op: str(props.op || props.operator),
      c: str(props.c || props.country),
      city: str(props.city),
      lat: num(props.lat),
      lon: num(props.lon),
      source: str(props.source),
      coordinate_precision: str(props.coordinate_precision),
      source_license: str(props.source_license),
      confidence: num(props.confidence),
      mapped_status: "mapped",
      net_count: num(props.net_count),
      ix_count: num(props.ix_count),
    };
    return { asset, type: "data_center" };
  }

  if (layerId === "globe-submarine-cable-lines") {
    const name = str(props.n || props.name);
    const sourceCable = data.cables.find((c) => c.n === name);
    return { asset: cableFromFeature(props, sourceCable), type: "submarine_cable" };
  }

  if (
    layerId === "globe-power-line-lines" ||
    layerId === "globe-power-line-cables" ||
    layerId === "globe-openinframap-power-line-lines" ||
    layerId === "globe-openinframap-power-line-cables"
  ) {
    return { asset: powerLineFromFeature(props), type: "power_line" };
  }

  return null;
}

function powerLineOpacity(layerOpacity: Record<string, number>, fallback = 0.72): number {
  return layerOpacity.power_lines ?? fallback;
}

function addGlobePowerLineLayers(
  m: maplibregl.Map,
  source: string,
  sourceLayer: string | undefined,
  ids: { overhead: string; cable: string },
  visible: boolean,
  filters: GridContinentFilters,
  opacity: number,
) {
  const sourceLayerProps = sourceLayer ? { "source-layer": sourceLayer } : {};
  m.addLayer({
    id: ids.overhead,
    type: "line",
    source,
    ...sourceLayerProps,
    minzoom: 2,
    filter: buildGridContinentFilter(POWER_OVERHEAD_FILTER, filters),
    layout: { visibility: visible ? "visible" : "none" },
    paint: {
      "line-color": powerLineColorExpression(),
      "line-width": ["interpolate", ["linear"], ["zoom"], 0, 0.35, 3, 0.85, 6, 1.8, 8, 2.8],
      "line-opacity": Math.min(opacity, 0.82),
    },
  });

  m.addLayer({
    id: ids.cable,
    type: "line",
    source,
    ...sourceLayerProps,
    minzoom: 2,
    filter: buildGridContinentFilter(POWER_CABLE_FILTER, filters),
    layout: { visibility: visible ? "visible" : "none" },
    paint: {
      "line-color": powerCableColorExpression(),
      "line-width": ["interpolate", ["linear"], ["zoom"], 0, 0.5, 3, 1.2, 6, 2.2, 8, 3.4],
      "line-opacity": Math.min(1, opacity + 0.14),
      "line-dasharray": [2, 1.2],
    },
  });
}

export default function GlobeAtlasMap({
  data,
  filters = DEFAULT_FILTERS,
  visibleLayers = DEFAULT_VISIBLE_LAYERS,
  graticuleVisible = true,
  proof = false,
  onAssetSelect,
  cableCompanyStats = [],
  cableFilters = DEFAULT_CABLE_FILTERS,
  navigateTo,
  core,
  powerLinesData = null,
  layerOpacity = {},
  gridContinentFilters = DEFAULT_GRID_CONTINENT_FILTERS,
  theme = "dark",
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const gridLayersAddedRef = useRef(false);
  const latestGridOptionsRef = useRef({ visibleLayers, gridContinentFilters, layerOpacity });
  const [layersReady, setLayersReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [camera, setCamera] = useState({ zoom: 1.05, center: "18.00, 8.00", bearing: 0 });

  const collections = useMemo(() => {
    const power = buildPowerPlantGeoJSON(data, filters);
    const dataCenters = buildDataCenterGeoJSON(data, filters);
    const cables = buildCableGeoJSON(data, cableFilters, cableCompanyStats);
    const graticule = buildGraticuleGeoJSON();
    return { power, dataCenters, cables, graticule };
  }, [data, filters, cableFilters, cableCompanyStats]);

  const tileStatus = useMemo(() => core ? getTileStatusFromCore(core) : null, [core]);
  const powerLineTileSources = useMemo(() => {
    if (!tileStatus) return {};
    if (tileStatus.power_lines !== "present" && tileStatus.openinframap_power_lines !== "present") return {};
    return getPMTilesSources(tileStatus, core?.tile_registry);
  }, [core, tileStatus]);
  const hasPowerLineTiles = Boolean(powerLineTileSources.power_lines_tiles || powerLineTileSources.openinframap_power_lines_tiles);
  const powerLineBounds = useMemo(() => {
    const geojsonBounds = powerLinesData ? computeFeatureCollectionBounds(powerLinesData) : null;
    return mergeBounds(
      geojsonBounds,
      boundsFromCore(core, "power_lines"),
      boundsFromCore(core, "openinframap_power_lines"),
    );
  }, [core, powerLinesData]);

  useEffect(() => {
    latestGridOptionsRef.current = { visibleLayers, gridContinentFilters, layerOpacity };
  }, [visibleLayers, gridContinentFilters, layerOpacity]);

  const fitToData = useCallback((duration = 500, maxZoom = 2.4) => {
    const m = mapRef.current;
    if (!m) return;

    const baseBounds = computeCombinedBounds([collections.power, collections.dataCenters, collections.cables]);
    const bounds = mergeBounds(baseBounds, visibleLayers.power_lines ? powerLineBounds : null);
    m.fitBounds(toFitBounds(paddedBounds(bounds || WORLD_BOUNDS)), {
      padding: 60,
      maxZoom,
      duration,
    });
  }, [collections, powerLineBounds, visibleLayers.power_lines]);

  const resetGlobalView = useCallback((duration = 700) => {
    const m = mapRef.current;
    if (!m) return;
    m.easeTo({ center: [18, 8], zoom: 1.05, bearing: 0, pitch: 0, duration });
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const m = new maplibregl.Map({
      container: containerRef.current,
      style: getGlobeTopoStyle(theme),
      center: [18, 8],
      zoom: 1.05,
      bearing: -8,
      pitch: 0,
      minZoom: 0,
      maxZoom: 8,
      renderWorldCopies: false,
      canvasContextAttributes: { preserveDrawingBuffer: true },
      attributionControl: { compact: true },
    });

    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

    m.on("error", (event) => {
      setError(event.error?.message || "MapLibre reported a globe render issue");
    });

    m.on("move", () => {
      const c = m.getCenter();
      setCamera({ zoom: m.getZoom(), center: `${c.lat.toFixed(2)}, ${c.lng.toFixed(2)}`, bearing: m.getBearing() });
    });

    const ensureElectricGridLayers = () => {
      if (gridLayersAddedRef.current || m.getZoom() < 2) return;
      gridLayersAddedRef.current = true;

      if (hasPowerLineTiles) {
        registerPMTilesProtocol();
        if (powerLineTileSources.power_lines_tiles && !m.getSource("globe-power-lines-tiles-source")) {
          m.addSource("globe-power-lines-tiles-source", powerLineTileSources.power_lines_tiles);
        }
        if (powerLineTileSources.openinframap_power_lines_tiles && !m.getSource("globe-openinframap-power-lines-tiles-source")) {
          m.addSource("globe-openinframap-power-lines-tiles-source", powerLineTileSources.openinframap_power_lines_tiles);
        }
      } else if (powerLinesData?.features?.length && !m.getSource("globe-power-lines-source")) {
        m.addSource("globe-power-lines-source", { type: "geojson", data: powerLinesData });
      }

      const latest = latestGridOptionsRef.current;
      const electricGridVisible = Boolean(latest.visibleLayers.power_lines);
      const gridOpacity = powerLineOpacity(latest.layerOpacity);
      if (m.getSource("globe-power-lines-tiles-source")) {
        addGlobePowerLineLayers(
          m,
          "globe-power-lines-tiles-source",
          "power_lines",
          { overhead: "globe-power-line-lines", cable: "globe-power-line-cables" },
          electricGridVisible,
          latest.gridContinentFilters,
          gridOpacity,
        );
      }
      if (m.getSource("globe-openinframap-power-lines-tiles-source")) {
        addGlobePowerLineLayers(
          m,
          "globe-openinframap-power-lines-tiles-source",
          "openinframap_power_lines",
          { overhead: "globe-openinframap-power-line-lines", cable: "globe-openinframap-power-line-cables" },
          electricGridVisible,
          latest.gridContinentFilters,
          gridOpacity,
        );
      }
      if (m.getSource("globe-power-lines-source")) {
        addGlobePowerLineLayers(
          m,
          "globe-power-lines-source",
          undefined,
          { overhead: "globe-power-line-lines", cable: "globe-power-line-cables" },
          electricGridVisible,
          latest.gridContinentFilters,
          gridOpacity,
        );
      }
    };

    m.on("load", () => {
      m.setProjection({ type: "globe" });
      m.resize();
      requestAnimationFrame(() => m.resize());

      m.addSource("globe-graticule-source", { type: "geojson", data: collections.graticule });
      m.addSource("globe-power-plants-source", {
        type: "geojson",
        data: collections.power,
      });
      m.addSource("globe-data-centers-source", { type: "geojson", data: collections.dataCenters });
      m.addSource("globe-submarine-cables-source", { type: "geojson", data: collections.cables });

      m.addLayer({
        id: "globe-graticule-lines",
        type: "line",
        source: "globe-graticule-source",
        layout: { visibility: graticuleVisible ? "visible" : "none" },
        paint: { "line-color": "rgba(219, 234, 254, 0.18)", "line-width": 0.8 },
      });

      m.addLayer({
        id: "globe-submarine-cable-lines",
        type: "line",
        source: "globe-submarine-cables-source",
        layout: { visibility: visibleLayers.cables ? "visible" : "none" },
        paint: {
          "line-color": ["coalesce", ["get", "operator_color"], CABLE_COLOR],
          "line-width": ["interpolate", ["linear"], ["zoom"], 0, 1.2, 3, 2.2, 7, 3.8],
          "line-opacity": ["case", ["boolean", ["get", "is_dimmed"], false], 0.18, 0.86],
        },
      });

      m.addLayer({
        id: "globe-power-points",
        type: "circle",
        source: "globe-power-plants-source",
        layout: { visibility: visibleLayers.power_plants ? "visible" : "none" },
        paint: {
          "circle-color": [
            "match", ["get", "f"],
            "Hydro", FUEL_COLORS.Hydro,
            "Solar", FUEL_COLORS.Solar,
            "Wind", FUEL_COLORS.Wind,
            "Natural Gas", FUEL_COLORS["Natural Gas"],
            "Nuclear", FUEL_COLORS.Nuclear,
            "Coal", FUEL_COLORS.Coal,
            "Oil", FUEL_COLORS.Oil,
            "Biomass", FUEL_COLORS.Biomass,
            "Geothermal", FUEL_COLORS.Geothermal,
            "Waste", FUEL_COLORS.Waste,
            "Cogeneration", FUEL_COLORS.Cogeneration,
            "Wave and Tidal", FUEL_COLORS["Wave and Tidal"],
            FUEL_COLORS.Other,
          ],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 2.2, 4, 4, 8, 6],
          "circle-opacity": 0.88,
          "circle-stroke-color": "rgba(255,255,255,0.68)",
          "circle-stroke-width": 0.7,
        },
      });

      m.addLayer({
        id: "globe-data-center-points",
        type: "circle",
        source: "globe-data-centers-source",
        layout: { visibility: visibleLayers.data_centers ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 4.2, 4, 6, 8, 8.5],
          "circle-color": DATA_CENTER_COLOR,
          "circle-opacity": 0.92,
          "circle-stroke-color": DATA_CENTER_STROKE_COLOR,
          "circle-stroke-width": 1.8,
        },
      });

      if (proof) {
        m.addSource("globe-proof-source", { type: "geojson", data: PROOF_POINTS });
        m.addLayer({
          id: "globe-proof-points",
          type: "circle",
          source: "globe-proof-source",
          paint: {
            "circle-radius": 10,
            "circle-color": "#ef4444",
            "circle-opacity": 0.95,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
          },
        });
      }

      setLayersReady(true);
      setError(null);
      ensureElectricGridLayers();
    });
    m.on("zoomend", ensureElectricGridLayers);
    m.on("moveend", ensureElectricGridLayers);

    const handleClick = (event: maplibregl.MapMouseEvent) => {
      const layers = INTERACTIVE_LAYERS.filter((id) => m.getLayer(id));
      const features = layers.length > 0 ? m.queryRenderedFeatures(event.point, { layers }) : [];
      if (!features.length) {
        onAssetSelect?.(null, null);
        return;
      }

      const feature = features[0];
      const assetResult = assetFromFeature(feature, data);
      if (assetResult) {
        onAssetSelect?.(assetResult.asset, assetResult.type);
        const [lon, lat] = featureLngLat(feature, event.lngLat);
        m.easeTo({ center: [lon, lat], duration: 450 });
      }
    };

    const handleMouseMove = (event: maplibregl.MapMouseEvent) => {
      const layers = INTERACTIVE_LAYERS.filter((id) => m.getLayer(id));
      const features = layers.length > 0 ? m.queryRenderedFeatures(event.point, { layers }) : [];
      m.getCanvas().style.cursor = features.length > 0 ? "pointer" : "";
    };

    m.on("click", handleClick);
    m.on("mousemove", handleMouseMove);
    m.on("mouseout", () => { m.getCanvas().style.cursor = ""; });

    mapRef.current = m;

    return () => {
      m.remove();
      mapRef.current = null;
      gridLayersAddedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !layersReady) return;

    (m.getSource("globe-power-plants-source") as maplibregl.GeoJSONSource | undefined)?.setData(collections.power);
    (m.getSource("globe-data-centers-source") as maplibregl.GeoJSONSource | undefined)?.setData(collections.dataCenters);
    (m.getSource("globe-submarine-cables-source") as maplibregl.GeoJSONSource | undefined)?.setData(collections.cables);
    if (powerLinesData) {
      (m.getSource("globe-power-lines-source") as maplibregl.GeoJSONSource | undefined)?.setData(powerLinesData);
    }
  }, [collections, layersReady, powerLinesData]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !layersReady) return;

    const setVisibility = (id: string, visible: boolean) => {
      if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    };

    setVisibility("globe-power-points", Boolean(visibleLayers.power_plants));
    setVisibility("globe-data-center-points", Boolean(visibleLayers.data_centers));
    setVisibility("globe-submarine-cable-lines", Boolean(visibleLayers.cables));
    setVisibility("globe-power-line-lines", Boolean(visibleLayers.power_lines));
    setVisibility("globe-power-line-cables", Boolean(visibleLayers.power_lines));
    setVisibility("globe-openinframap-power-line-lines", Boolean(visibleLayers.power_lines));
    setVisibility("globe-openinframap-power-line-cables", Boolean(visibleLayers.power_lines));
    setVisibility("globe-graticule-lines", graticuleVisible);
  }, [visibleLayers, graticuleVisible, layersReady]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !layersReady) return;
    const overheadFilter = buildGridContinentFilter(POWER_OVERHEAD_FILTER, gridContinentFilters);
    const cableFilter = buildGridContinentFilter(POWER_CABLE_FILTER, gridContinentFilters);

    const setFilter = (id: string, filter: maplibregl.FilterSpecification) => {
      if (m.getLayer(id)) m.setFilter(id, filter);
    };

    setFilter("globe-power-line-lines", overheadFilter);
    setFilter("globe-openinframap-power-line-lines", overheadFilter);
    setFilter("globe-power-line-cables", cableFilter);
    setFilter("globe-openinframap-power-line-cables", cableFilter);
  }, [gridContinentFilters, layersReady]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !layersReady) return;
    const opacity = powerLineOpacity(layerOpacity);
    const setOpacity = (id: string, value: number) => {
      if (m.getLayer(id)) m.setPaintProperty(id, "line-opacity", value);
    };
    setOpacity("globe-power-line-lines", Math.min(opacity, 0.82));
    setOpacity("globe-openinframap-power-line-lines", Math.min(opacity, 0.82));
    setOpacity("globe-power-line-cables", Math.min(1, opacity + 0.14));
    setOpacity("globe-openinframap-power-line-cables", Math.min(1, opacity + 0.14));
  }, [layerOpacity, layersReady]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !navigateTo) return;

    if (navigateTo.bounds) {
      m.fitBounds(toFitBounds(paddedBounds(navigateTo.bounds, 2)), {
        padding: 80,
        maxZoom: navigateTo.zoom ?? 4.5,
        duration: 900,
      });
      return;
    }

    m.flyTo({ center: [navigateTo.lon, navigateTo.lat], zoom: navigateTo.zoom ?? 4, duration: 1000 });
  }, [navigateTo]);

  return (
    <div className="globe-atlas">
      <div ref={containerRef} className="globe-atlas-map" />

      <div className="globe-controls" aria-label="Globe controls">
        <button type="button" onClick={() => resetGlobalView()} title="Reset global view">
          Reset
        </button>
        <button type="button" onClick={() => fitToData(700, 3.5)} title="Fit visible data">
          Fit Data
        </button>
      </div>

      {!layersReady && !error && (
        <div className="globe-status">Preparing globe layers...</div>
      )}

      {error && (
        <div className="globe-status globe-status--error">
          <strong>Globe renderer issue</strong>
          <span>{error}</span>
        </div>
      )}

      {proof && (
        <div className="globe-debug">
          <div className="globe-debug-title">GLOBE PROTOTYPE</div>
          <div>MapLibre: {layersReady ? "ready" : "loading"}</div>
          <div>Power features: {collections.power.features.length.toLocaleString()}</div>
          <div>Data centers: {collections.dataCenters.features.length.toLocaleString()}</div>
          <div>Cables: {collections.cables.features.length.toLocaleString()}</div>
          <div>Zoom: {camera.zoom.toFixed(2)}</div>
          <div>Center: {camera.center}</div>
          <div>Bearing: {camera.bearing.toFixed(1)}</div>
        </div>
      )}
    </div>
  );
}
