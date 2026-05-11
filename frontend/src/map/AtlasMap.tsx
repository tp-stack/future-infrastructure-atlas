import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset, PowerPlant, DataCenter } from "./types";
import { LAYER_IDS, POWER_PAINT, DATA_CENTER_PAINT, CABLE_PAINT, CLUSTER_PAINT, CLUSTER_COUNT_PAINT } from "./layers";
import InfrastructureCanvasOverlay from "./InfrastructureCanvasOverlay";
import type { CanvasDiagnostics, AssetHit } from "./InfrastructureCanvasOverlay";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  onPopup: (asset: Asset | null) => void;
  onDiagnostics?: (diag: MapDiagnostics) => void;
  onCanvasDiagnostics?: (d: CanvasDiagnostics) => void;
  showTestPoints?: boolean;
}

export interface MapDiagnostics {
  basemap: string;
  layers_ok: string[];
  layers_failed: { layer: string; error: string }[];
  total_points: number;
  data_bounds: string;
  status: "ok" | "partial" | "failed";
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
    {
      id: "background",
      type: "background" as const,
      paint: { "background-color": DARK_BG },
    },
    {
      id: "basemap-dark-layer",
      type: "raster" as const,
      source: "basemap-dark",
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

function computeDataBounds(data: AtlasData): maplibregl.LngLatBounds | null {
  const bounds = new maplibregl.LngLatBounds();
  let hasData = false;
  for (const p of data.power_plants) {
    bounds.extend([p.lon, p.lat]);
    hasData = true;
  }
  for (const d of data.data_centers) {
    if (d.lat != null && d.lon != null) {
      bounds.extend([d.lon, d.lat]);
      hasData = true;
    }
  }
  return hasData ? bounds : null;
}

export default function AtlasMap({ data, filters, visibleLayers, onPopup, onDiagnostics, onCanvasDiagnostics, showTestPoints }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [loaded, setLoaded] = useState(false);

  const handleCanvasClick = useCallback((hit: AssetHit | null) => {
    if (!hit) { onPopup(null); return; }
    if (hit.type === "power_plant") {
      const p = hit.asset as PowerPlant;
      onPopup({
        n: p.n, c: p.c, f: p.f, mw: p.mw, lat: p.lat, lon: p.lon, mapped_status: "mapped",
      } as Asset);
    } else if (hit.type === "data_center") {
      const d = hit.asset as DataCenter;
      onPopup({
        n: d.n, op: d.op, c: d.c, city: d.city, lat: d.lat, lon: d.lon,
        mw: d.mw, source: d.source, mapped_status: d.mapped_status,
        coordinate_precision: d.coordinate_precision, confidence: d.confidence,
      } as Asset);
    }
  }, [onPopup]);

  const initMap = useCallback(() => {
    if (!mapContainer.current || map.current) return;
    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: CARTO_DARK_STYLE,
      center: [10, 30],
      zoom: 1.8,
      renderWorldCopies: false,
      maxBounds: [[-180, -85], [180, 85]],
    });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
    map.current = m;

    m.on("load", () => {
      const diag: MapDiagnostics = {
        basemap: "CARTO dark",
        layers_ok: [],
        layers_failed: [],
        total_points: data.power_plants.length + data.data_centers.filter((d) => d.lat != null && d.lon != null).length,
        data_bounds: "",
        status: "ok",
      };

      // MapLibre layers are secondary — canvas overlay is primary renderer
      addPowerPlantLayer(m, data, diag);
      addCableLayer(m, data, diag);
      addDataCenterLayer(m, data, diag);

      const diagFails = diag.layers_failed.length;
      if (diagFails > 0) {
        diag.status = diag.layers_ok.length > 0 ? "partial" : "failed";
      }

      const bounds = computeDataBounds(data);
      if (bounds) {
        diag.data_bounds = `${bounds.getWest().toFixed(1)},${bounds.getSouth().toFixed(1)} to ${bounds.getEast().toFixed(1)},${bounds.getNorth().toFixed(1)}`;
        m.fitBounds(bounds, { padding: 60, maxZoom: 8, animate: false });
      }

      onDiagnostics?.(diag);
      setLoaded(true);
    });

    m.on("click", LAYER_IDS.POWER_CLUSTERS, (e) => {
      const features = m.queryRenderedFeatures(e.point, { layers: [LAYER_IDS.POWER_CLUSTERS] });
      if (!features.length) return;
      const clusterId = features[0].properties?.cluster_id as number | undefined;
      const source = m.getSource(LAYER_IDS.POWER_PLANTS) as maplibregl.GeoJSONSource;
      if (clusterId != null && source) {
        const geometry = features[0].geometry as GeoJSON.Point;
        source.getClusterExpansionZoom(clusterId).then((zoom: number) => {
          m.easeTo({ center: geometry.coordinates as [number, number], zoom: zoom + 1 });
        });
      }
    });

    m.on("mouseenter", [LAYER_IDS.POWER_CLUSTERS, LAYER_IDS.POWER_PLANTS, LAYER_IDS.DATA_CENTERS, LAYER_IDS.CABLES], () => {
      m.getCanvas().style.cursor = "pointer";
    });
    m.on("mouseleave", [LAYER_IDS.POWER_CLUSTERS, LAYER_IDS.POWER_PLANTS, LAYER_IDS.DATA_CENTERS, LAYER_IDS.CABLES], () => {
      m.getCanvas().style.cursor = "";
    });
  }, [data, onPopup, onDiagnostics]);

  useEffect(() => {
    initMap();
    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [initMap]);

  useEffect(() => {
    if (!map.current || !loaded) return;
    const toggleCluster = visibleLayers.power_plants ? "visible" : "none" as unknown as string;
    map.current.setLayoutProperty(LAYER_IDS.POWER_CLUSTERS, "visibility", toggleCluster);
    map.current.setLayoutProperty(LAYER_IDS.POWER_CLUSTER_COUNT, "visibility", toggleCluster);
    map.current.setLayoutProperty(LAYER_IDS.POWER_PLANTS, "visibility", toggleCluster);
  }, [visibleLayers.power_plants, loaded]);

  useEffect(() => {
    if (!map.current || !loaded) return;
    map.current.setLayoutProperty(LAYER_IDS.CABLES, "visibility", (visibleLayers.cables ? "visible" : "none") as unknown as string);
  }, [visibleLayers.cables, loaded]);

  useEffect(() => {
    if (!map.current || !loaded) return;
    map.current.setLayoutProperty(LAYER_IDS.DATA_CENTERS, "visibility", (visibleLayers.data_centers ? "visible" : "none") as unknown as string);
  }, [visibleLayers.data_centers, loaded]);

  useEffect(() => {
    if (!map.current || !loaded) return;
    applyFilters(map.current, filters);
  }, [filters, loaded]);

  const handleResetView = useCallback(() => {
    if (!map.current) return;
    map.current.flyTo({ center: [10, 30], zoom: 1.8 });
  }, []);

  const handleFitData = useCallback(() => {
    if (!map.current) return;
    const bounds = computeDataBounds(data);
    if (bounds) {
      map.current.fitBounds(bounds, { padding: 60, maxZoom: 10 });
    }
  }, [data]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="map-canvas" />
      <InfrastructureCanvasOverlay
        data={data}
        filters={filters}
        visibleLayers={visibleLayers}
        mapInstance={map.current}
        mapLoaded={loaded}
        showTestPoints={showTestPoints}
        onCanvasDiagnostics={onCanvasDiagnostics}
        onCanvasClick={handleCanvasClick}
      />
      <div className="map-overlay-controls">
        <button className="map-ctrl-btn" onClick={handleResetView} title="Reset view">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
        <button className="map-ctrl-btn" onClick={handleFitData} title="Fit to data">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        </button>
      </div>
    </div>
  );
}

// MapLibre layers — secondary, kept for clustering zoom and future use
function addPowerPlantLayer(m: maplibregl.Map, data: AtlasData, diag: MapDiagnostics) {
  try {
    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: data.power_plants.map((p) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] },
        properties: { n: p.n, c: p.c, f: p.f, mw: p.mw },
      })),
    };
    m.addSource(LAYER_IDS.POWER_PLANTS, { type: "geojson", data: geojson, cluster: true, clusterMaxZoom: 14, clusterRadius: 40 });
    m.addLayer({ id: LAYER_IDS.POWER_CLUSTERS, type: "circle", source: LAYER_IDS.POWER_PLANTS, filter: ["has", "point_count"], paint: CLUSTER_PAINT as any });
    m.addLayer({ id: LAYER_IDS.POWER_CLUSTER_COUNT, type: "symbol", source: LAYER_IDS.POWER_PLANTS, filter: ["has", "point_count"], layout: CLUSTER_COUNT_PAINT as any, paint: {} });
    m.addLayer({ id: LAYER_IDS.POWER_PLANTS, type: "circle", source: LAYER_IDS.POWER_PLANTS, filter: ["!", ["has", "point_count"]], paint: POWER_PAINT as any });
    diag.layers_ok.push("power_plants");
  } catch (e) {
    diag.layers_failed.push({ layer: "power_plants", error: String(e) });
  }
}

function addCableLayer(m: maplibregl.Map, data: AtlasData, diag: MapDiagnostics) {
  try {
    const withGeom = data.cables.filter((c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length >= 2);
    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: withGeom.map((c) => ({
        type: "Feature" as const,
        geometry: { type: "LineString" as const, coordinates: c.geometry },
        properties: { n: c.n },
      })),
    };
    m.addSource(LAYER_IDS.CABLES, { type: "geojson", data: geojson });
    m.addLayer({ id: LAYER_IDS.CABLES, type: "line", source: LAYER_IDS.CABLES, paint: CABLE_PAINT as any, layout: { visibility: "visible" as const } });
    diag.layers_ok.push("cables");
  } catch (e) {
    diag.layers_failed.push({ layer: "cables", error: String(e) });
  }
}

function addDataCenterLayer(m: maplibregl.Map, data: AtlasData, diag: MapDiagnostics) {
  try {
    const withCoords = data.data_centers.filter((d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null);
    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: withCoords.map((d) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [d.lon, d.lat] },
        properties: { n: d.n },
      })),
    };
    m.addSource(LAYER_IDS.DATA_CENTERS, { type: "geojson", data: geojson });
    m.addLayer({ id: LAYER_IDS.DATA_CENTERS, type: "circle", source: LAYER_IDS.DATA_CENTERS, paint: DATA_CENTER_PAINT as any, layout: { visibility: "visible" as const } });
    diag.layers_ok.push("data_centers");
  } catch (e) {
    diag.layers_failed.push({ layer: "data_centers", error: String(e) });
  }
}

function applyFilters(m: maplibregl.Map, filters: FilterState) {
  const filtersArr: any[] = [];
  if (filters.fuelType) filtersArr.push(["==", ["get", "f"], filters.fuelType]);
  if (filters.country) filtersArr.push(["in", filters.country, ["get", "c"]]);
  if (filters.minMw > 0) filtersArr.push([">=", ["get", "mw"], filters.minMw]);
  if (filtersArr.length > 0) {
    m.setFilter(LAYER_IDS.POWER_PLANTS, ["all" as any, ...filtersArr] as any);
  } else {
    m.setFilter(LAYER_IDS.POWER_PLANTS, ["!", ["has", "point_count"]]);
  }
}
