import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, Asset, FilterState } from "./types";
import type { InteractableType } from "./interaction";
import { MAPLIBRE_GLYPHS_URL } from "./basemaps";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS } from "./layers";
import type { CableCompanyStat, CableFilterState } from "./cables";
import { DEFAULT_CABLE_FILTERS } from "./cables";
import {
  buildCableGeoJSON,
  buildDataCenterGeoJSON,
  buildGraticuleGeoJSON,
  buildPowerPlantGeoJSON,
  computeCombinedBounds,
  type LonLatBounds,
} from "./geojson";

interface Props {
  data: AtlasData;
  filters?: FilterState;
  visibleLayers?: Record<string, boolean>;
  graticuleVisible?: boolean;
  proof?: boolean;
  onAssetSelect?: (asset: Asset | null, assetType: InteractableType | null) => void;
  cableCompanyStats?: CableCompanyStat[];
  cableFilters?: CableFilterState;
}

const DEFAULT_FILTERS: FilterState = { fuelType: "", country: "", minMw: 0 };
const DEFAULT_VISIBLE_LAYERS = { power_plants: true, cables: true, data_centers: true };
const WORLD_BOUNDS: LonLatBounds = { minLon: -179.5, minLat: -60, maxLon: 179.5, maxLat: 85 };
const INTERACTIVE_LAYERS = [
  "power-points",
  "data-center-points",
  "submarine-cable-lines",
  "proof-points",
];

const DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  name: "Clean Zoomable Infrastructure Atlas",
  glyphs: MAPLIBRE_GLYPHS_URL,
  sources: {},
  layers: [
    {
      id: "atlas-background",
      type: "background",
      paint: { "background-color": "#05070a" },
    },
  ],
};

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

function popupRows(rows: Array<[string, unknown]>): string {
  return rows
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([label, value]) => (
      `<div class="popup-row"><span class="popup-label">${escapeHtml(label)}</span><span class="popup-val">${escapeHtml(String(value))}</span></div>`
    ))
    .join("");
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function featureLngLat(feature: maplibregl.MapGeoJSONFeature, fallback: maplibregl.LngLat): [number, number] {
  if (feature.geometry.type === "Point") {
    const coords = (feature.geometry as GeoJSON.Point).coordinates;
    if (Number.isFinite(coords[0]) && Number.isFinite(coords[1])) return [coords[0], coords[1]];
  }
  return [fallback.lng, fallback.lat];
}

function assetFromFeature(feature: maplibregl.MapGeoJSONFeature): { asset: Asset; type: InteractableType } | null {
  const props = feature.properties as Record<string, unknown>;
  const layerId = feature.layer?.id;

  if (layerId === "power-points") {
    return {
      type: "power_plant",
      asset: {
        kind: "power_plant",
        n: String(props.n || props.name || ""),
        c: String(props.c || props.country || ""),
        f: String(props.f || props.fuel || ""),
        mw: Number(props.mw ?? props.capacity_mw ?? 0),
        lat: Number(props.lat ?? 0),
        lon: Number(props.lon ?? 0),
      },
    };
  }

  if (layerId === "data-center-points") {
    return {
      type: "data_center",
      asset: {
        kind: "data_center",
        n: String(props.n || props.name || ""),
        op: String(props.op || props.operator || ""),
        c: String(props.c || props.country || ""),
        city: String(props.city || ""),
        lat: Number(props.lat ?? 0),
        lon: Number(props.lon ?? 0),
        source: String(props.source || ""),
        coordinate_precision: String(props.coordinate_precision || ""),
        source_license: String(props.source_license || ""),
        confidence: Number(props.confidence ?? 0),
        mapped_status: "mapped",
        net_count: Number(props.net_count ?? 0),
        ix_count: Number(props.ix_count ?? 0),
      },
    };
  }

  if (layerId === "submarine-cable-lines") {
    return {
      type: "submarine_cable",
      asset: {
        kind: "submarine_cable",
        n: String(props.n || props.name || ""),
        source: String(props.source || ""),
        geometry: [],
        mapped_status: "mapped",
        source_license: String(props.source_license || ""),
        geometry_precision: String(props.geometry_precision || ""),
        confidence: Number(props.confidence ?? 0),
        operators: String(props.operators || ""),
        landing_points: String(props.landing_points || ""),
        length_km: String(props.length_km || ""),
      },
    };
  }

  return null;
}

export default function ZoomableAtlasMap({
  data,
  filters = DEFAULT_FILTERS,
  visibleLayers = DEFAULT_VISIBLE_LAYERS,
  graticuleVisible = true,
  proof = false,
  onAssetSelect,
  cableCompanyStats = [],
  cableFilters = DEFAULT_CABLE_FILTERS,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [layersReady, setLayersReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [camera, setCamera] = useState({ zoom: 1.3, center: "20.00, 10.00" });

  const collections = useMemo(() => {
    const power = buildPowerPlantGeoJSON(data, filters);
    const dataCenters = buildDataCenterGeoJSON(data, filters);
    const cables = buildCableGeoJSON(data, cableFilters, cableCompanyStats);
    const graticule = buildGraticuleGeoJSON();
    return { power, dataCenters, cables, graticule };
  }, [data, filters, cableFilters, cableCompanyStats]);

  const fitToData = useCallback((duration = 0, maxZoom = 2.8) => {
    const m = mapRef.current;
    if (!m) return;

    const bounds = computeCombinedBounds([collections.power, collections.dataCenters, collections.cables]);
    if (!bounds) {
      m.fitBounds(toFitBounds(WORLD_BOUNDS), { padding: 50, maxZoom, duration });
      return;
    }

    m.fitBounds(toFitBounds(paddedBounds(bounds)), { padding: 50, maxZoom, duration });
  }, [collections]);

  const resetGlobalView = useCallback((duration = 500) => {
    mapRef.current?.fitBounds(toFitBounds(WORLD_BOUNDS), { padding: 30, maxZoom: 2.5, duration });
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const m = new maplibregl.Map({
      container: containerRef.current,
      style: DARK_STYLE,
      center: [10, 20],
      zoom: 1.3,
      renderWorldCopies: false,
      canvasContextAttributes: { preserveDrawingBuffer: true },
      maxBounds: [[-179.5, -85], [179.5, 85]],
    });

    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");

    m.on("error", (event) => {
      setError(event.error?.message || "MapLibre reported a render issue");
    });

    m.on("move", () => {
      const c = m.getCenter();
      setCamera({ zoom: m.getZoom(), center: `${c.lat.toFixed(2)}, ${c.lng.toFixed(2)}` });
    });

    m.on("load", () => {
      m.resize();
      requestAnimationFrame(() => m.resize());

      m.addSource("graticule-source", { type: "geojson", data: collections.graticule });
      m.addSource("power-plants-source", {
        type: "geojson",
        data: collections.power,
      });
      m.addSource("data-centers-source", { type: "geojson", data: collections.dataCenters });
      m.addSource("submarine-cables-source", { type: "geojson", data: collections.cables });

      m.addLayer({
        id: "graticule-lines",
        type: "line",
        source: "graticule-source",
        layout: { visibility: graticuleVisible ? "visible" : "none" },
        paint: { "line-color": "rgba(148, 163, 184, 0.2)", "line-width": 0.7 },
      });

      m.addLayer({
        id: "submarine-cable-lines",
        type: "line",
        source: "submarine-cables-source",
        layout: { visibility: visibleLayers.cables ? "visible" : "none" },
        paint: {
          "line-color": ["coalesce", ["get", "operator_color"], CABLE_COLOR],
          "line-width": ["interpolate", ["linear"], ["zoom"], 0, 1.6, 4, 2.8, 8, 4],
          "line-opacity": ["case", ["boolean", ["get", "is_dimmed"], false], 0.22, 0.95],
        },
      });

      m.addLayer({
        id: "power-points",
        type: "circle",
        source: "power-plants-source",
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
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 2.5, 5, 4, 9, 6],
          "circle-opacity": 0.9,
          "circle-stroke-color": "rgba(255,255,255,0.75)",
          "circle-stroke-width": 0.7,
        },
      });

      m.addLayer({
        id: "data-center-points",
        type: "circle",
        source: "data-centers-source",
        layout: { visibility: visibleLayers.data_centers ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 0, 4.5, 5, 6.5, 9, 9],
          "circle-color": DATA_CENTER_COLOR,
          "circle-opacity": 0.94,
          "circle-stroke-color": DATA_CENTER_STROKE_COLOR,
          "circle-stroke-width": 2,
        },
      });

      if (proof) {
        m.addSource("proof-source", { type: "geojson", data: PROOF_POINTS });
        m.addLayer({
          id: "proof-points",
          type: "circle",
          source: "proof-source",
          paint: {
            "circle-radius": 12,
            "circle-color": "#ef4444",
            "circle-opacity": 0.95,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 3,
          },
        });
      }

      setLayersReady(true);
      setError(null);
      setTimeout(() => fitToData(0), 80);
    });

    const handleClick = (event: maplibregl.MapMouseEvent) => {
      const layers = INTERACTIVE_LAYERS.filter((id) => m.getLayer(id));
      const features = layers.length > 0 ? m.queryRenderedFeatures(event.point, { layers }) : [];
      if (!features.length) {
        popupRef.current?.remove();
        onAssetSelect?.(null, null);
        return;
      }

      const feature = features[0];
      const props = feature.properties as Record<string, unknown>;
      let title = String(props.n || props.name || "Infrastructure asset");
      let rows: Array<[string, unknown]> = [];
      const assetResult = assetFromFeature(feature);

      if (feature.layer?.id === "power-points") {
        rows = [["Fuel", props.f || props.fuel], ["Capacity", props.mw ? `${props.mw} MW` : props.capacity_mw], ["Country", props.c || props.country]];
      } else if (feature.layer?.id === "data-center-points") {
        rows = [["Operator", props.op || props.operator], ["Country", props.c || props.country], ["City", props.city], ["Precision", props.coordinate_precision], ["Source", props.source]];
      } else if (feature.layer?.id === "submarine-cable-lines") {
        rows = [["Source", props.source], ["License", props.source_license], ["Precision", props.geometry_precision], ["Confidence", props.confidence]];
      } else if (feature.layer?.id === "proof-points") {
        title = String(props.n || "Proof point");
        rows = [["Proof route", "visible"]];
      }

      popupRef.current?.remove();
      popupRef.current = new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: "320px" })
        .setLngLat(featureLngLat(feature, event.lngLat))
        .setHTML(`<div class="popup-content"><div class="popup-header">${escapeHtml(title)}</div>${popupRows(rows)}</div>`)
        .addTo(m);

      if (assetResult) onAssetSelect?.(assetResult.asset, assetResult.type);
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
    (window as unknown as { __atlasZoomMap?: maplibregl.Map }).__atlasZoomMap = m;

    return () => {
      popupRef.current?.remove();
      delete (window as unknown as { __atlasZoomMap?: maplibregl.Map }).__atlasZoomMap;
      m.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !layersReady) return;

    (m.getSource("power-plants-source") as maplibregl.GeoJSONSource | undefined)?.setData(collections.power);
    (m.getSource("data-centers-source") as maplibregl.GeoJSONSource | undefined)?.setData(collections.dataCenters);
    (m.getSource("submarine-cables-source") as maplibregl.GeoJSONSource | undefined)?.setData(collections.cables);
  }, [collections, layersReady]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !layersReady) return;

    const setVisibility = (id: string, visible: boolean) => {
      if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    };

    setVisibility("power-points", visibleLayers.power_plants);
    setVisibility("data-center-points", visibleLayers.data_centers);
    setVisibility("submarine-cable-lines", visibleLayers.cables);
    setVisibility("graticule-lines", graticuleVisible);
  }, [visibleLayers, graticuleVisible, layersReady]);

  return (
    <div className="zoomable-atlas">
      <div ref={containerRef} className="zoomable-atlas-map" />

      <div className="zoomable-debug">
        <div className="zoomable-debug-title">{proof ? "PROOF MAP" : "ZOOMABLE MAP"}</div>
        <div>MapLibre: {layersReady ? "ready" : "loading"}</div>
        <div>Power features: {collections.power.features.length.toLocaleString()}</div>
        <div>Data centers: {collections.dataCenters.features.length.toLocaleString()}</div>
        <div>Cable features: {collections.cables.features.length.toLocaleString()}</div>
        <div>Zoom: {camera.zoom.toFixed(2)}</div>
        <div>Center: {camera.center}</div>
        {proof && <div className="zoomable-proof-label">5 proof points enabled</div>}
        {error && <div className="zoomable-error">{error}</div>}
      </div>

      <div className="zoomable-controls">
        <button type="button" onClick={() => resetGlobalView()} title="Reset Global View">
          Reset Global View
        </button>
        <button type="button" onClick={() => fitToData(500, 4)} title="Fit Filtered Results">
          Fit Filtered Results
        </button>
      </div>
    </div>
  );
}
