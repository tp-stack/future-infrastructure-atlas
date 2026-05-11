import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset, PowerPlant } from "./types";
import { LAYER_IDS, POWER_PAINT, DATA_CENTER_PAINT, CABLE_PAINT, CLUSTER_PAINT, CLUSTER_COUNT_PAINT } from "./layers";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  onPopup: (asset: Asset | null) => void;
  onDiagnostics?: (diag: MapDiagnostics) => void;
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

type SourceSpec = maplibregl.SourceSpecification | maplibregl.CanvasSourceSpecification;
type LayerSpec = maplibregl.LayerSpecification;

function safeAddSource(m: maplibregl.Map, id: string, source: SourceSpec): boolean {
  try {
    if (m.getSource(id)) return true;
    m.addSource(id, source);
    return true;
  } catch (e) {
    console.warn(`[AtlasMap] Failed to add source "${id}":`, e);
    return false;
  }
}

function safeAddLayer(m: maplibregl.Map, layer: LayerSpec): boolean {
  try {
    if (m.getLayer(layer.id)) return true;
    m.addLayer(layer);
    return true;
  } catch (e) {
    console.warn(`[AtlasMap] Failed to add layer "${layer.id}":`, e);
    return false;
  }
}

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

export default function AtlasMap({ data, filters, visibleLayers, onPopup, onDiagnostics }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [loaded, setLoaded] = useState(false);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

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

    m.on("click", LAYER_IDS.POWER_PLANTS, (e) => {
      if (!e.features || e.features.length === 0) return;
      const f = e.features[0];
      const props = f.properties as Record<string, unknown>;
      const coords = (f.geometry as GeoJSON.Point).coordinates;
      const plant: Asset = {
        n: (props.n as string) || "",
        c: (props.c as string) || "",
        f: (props.f as string) || "",
        mw: (props.mw as number) || 0,
        lat: coords[1],
        lon: coords[0],
        mapped_status: "mapped",
      };
      showPlantPopup(m, popupRef, plant, e.originalEvent);
      onPopup(plant);
    });

    m.on("click", LAYER_IDS.DATA_CENTERS, (e) => {
      if (!e.features || e.features.length === 0) return;
      const f = e.features[0];
      const props = f.properties as Record<string, unknown>;
      const coords = (f.geometry as GeoJSON.Point).coordinates;
      const dc: Asset = {
        n: (props.n as string) || "",
        op: (props.op as string) || "",
        c: (props.c as string) || "",
        city: (props.city as string) || "",
        lat: coords[1],
        lon: coords[0],
        mw: (props.mw as number) ?? null,
        source: (props.source as string) || "",
        mapped_status: (props.mapped_status as "mapped") || "mapped",
        coordinate_precision: (props.coordinate_precision as string) || "",
        confidence: (props.confidence as number) || undefined,
      };
      showDCPopup(m, popupRef, dc, e.originalEvent);
      onPopup(dc);
    });

    m.on("click", LAYER_IDS.CABLES, (e) => {
      if (!e.features || e.features.length === 0) return;
      const f = e.features[0];
      const props = f.properties as Record<string, unknown>;
      const cable: Asset = {
        n: (props.n as string) || "",
        source: (props.source as string) || "",
        geometry: [],
        mapped_status: (props.mapped_status as "mapped") || "mapped",
        geometry_precision: (props.geometry_precision as string) || "",
        confidence: (props.confidence as number) || undefined,
      };
      showCablePopup(m, popupRef, cable, e.lngLat, e.originalEvent);
      onPopup(cable);
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

    if (mapContainer.current) {
      resizeObserverRef.current = new ResizeObserver(() => {
        map.current?.resize();
      });
      resizeObserverRef.current.observe(mapContainer.current.parentElement!);
    }

    return () => {
      resizeObserverRef.current?.disconnect();
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
    map.current.setLayoutProperty(
      LAYER_IDS.CABLES,
      "visibility",
      (visibleLayers.cables ? "visible" : "none") as unknown as string
    );
  }, [visibleLayers.cables, loaded]);

  useEffect(() => {
    if (!map.current || !loaded) return;
    map.current.setLayoutProperty(
      LAYER_IDS.DATA_CENTERS,
      "visibility",
      (visibleLayers.data_centers ? "visible" : "none") as unknown as string
    );
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

function addPowerPlantLayer(m: maplibregl.Map, data: AtlasData, diag: MapDiagnostics) {
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: data.power_plants.map((p) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] },
      properties: { n: p.n, c: p.c, f: p.f, mw: p.mw },
    })),
  };

  if (!safeAddSource(m, LAYER_IDS.POWER_PLANTS, {
    type: "geojson",
    data: geojson,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 40,
  })) {
    diag.layers_failed.push({ layer: "power_plants", error: "Failed to add source" });
    return;
  }

  if (safeAddLayer(m, {
    id: LAYER_IDS.POWER_CLUSTERS,
    type: "circle",
    source: LAYER_IDS.POWER_PLANTS,
    filter: ["has", "point_count"],
    paint: CLUSTER_PAINT as unknown as maplibregl.CircleLayerSpecification["paint"],
  })) {
    diag.layers_ok.push("power_plants_clusters");
  } else {
    diag.layers_failed.push({ layer: "power_plants_clusters", error: "Failed to add cluster layer" });
  }

  if (safeAddLayer(m, {
    id: LAYER_IDS.POWER_CLUSTER_COUNT,
    type: "symbol",
    source: LAYER_IDS.POWER_PLANTS,
    filter: ["has", "point_count"],
    layout: CLUSTER_COUNT_PAINT as unknown as maplibregl.SymbolLayerSpecification["layout"],
    paint: {},
  })) {
    diag.layers_ok.push("power_plants_cluster_count");
  } else {
    diag.layers_failed.push({ layer: "power_plants_cluster_count", error: "Failed to add cluster count layer" });
  }

  if (safeAddLayer(m, {
    id: LAYER_IDS.POWER_PLANTS,
    type: "circle",
    source: LAYER_IDS.POWER_PLANTS,
    filter: ["!", ["has", "point_count"]],
    paint: POWER_PAINT as unknown as maplibregl.CircleLayerSpecification["paint"],
  })) {
    diag.layers_ok.push("power_plants");
  } else {
    diag.layers_failed.push({ layer: "power_plants", error: "Failed to add plant layer" });
  }
}

function addCableLayer(m: maplibregl.Map, data: AtlasData, diag: MapDiagnostics) {
  const withGeom = data.cables.filter((c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length >= 2);
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: withGeom.map((c) => ({
      type: "Feature" as const,
      geometry: { type: "LineString" as const, coordinates: c.geometry },
      properties: { n: c.n, source: c.source, mapped_status: c.mapped_status, geometry_precision: c.geometry_precision, confidence: c.confidence },
    })),
  };

  if (!safeAddSource(m, LAYER_IDS.CABLES, { type: "geojson", data: geojson })) {
    diag.layers_failed.push({ layer: "cables", error: "Failed to add source" });
    return;
  }

  if (safeAddLayer(m, {
    id: LAYER_IDS.CABLES,
    type: "line",
    source: LAYER_IDS.CABLES,
    paint: CABLE_PAINT as unknown as maplibregl.LineLayerSpecification["paint"],
    layout: { visibility: "visible" as const },
  })) {
    diag.layers_ok.push("cables");
  } else {
    diag.layers_failed.push({ layer: "cables", error: "Failed to add cable layer" });
  }
}

function addDataCenterLayer(m: maplibregl.Map, data: AtlasData, diag: MapDiagnostics) {
  const withCoords = data.data_centers.filter((d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null);
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: withCoords.map((d) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [d.lon, d.lat] },
      properties: { n: d.n, op: d.op, c: d.c, city: d.city, mw: d.mw, source: d.source, mapped_status: d.mapped_status, coordinate_precision: d.coordinate_precision, confidence: d.confidence },
    })),
  };

  if (!safeAddSource(m, LAYER_IDS.DATA_CENTERS, { type: "geojson", data: geojson })) {
    diag.layers_failed.push({ layer: "data_centers", error: "Failed to add source" });
    return;
  }

  if (safeAddLayer(m, {
    id: LAYER_IDS.DATA_CENTERS,
    type: "circle",
    source: LAYER_IDS.DATA_CENTERS,
    paint: DATA_CENTER_PAINT as unknown as maplibregl.CircleLayerSpecification["paint"],
    layout: { visibility: "visible" as const },
  })) {
    diag.layers_ok.push("data_centers");
  } else {
    diag.layers_failed.push({ layer: "data_centers", error: "Failed to add DC layer" });
  }
}

function showPlantPopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, plant: Asset, event?: MouseEvent | PointerEvent) {
  if (popupRef.current) popupRef.current.remove();
  if (!("f" in plant)) return;
  const html = `
    <div class="popup-content">
      <div class="popup-header">${escapeHtml(plant.n)}</div>
      <div class="popup-row"><span class="popup-label">Type</span><span class="popup-val">Power Plant</span></div>
      <div class="popup-row"><span class="popup-label">Fuel</span><span class="popup-val">${escapeHtml(plant.f)}</span></div>
      <div class="popup-row"><span class="popup-label">Capacity</span><span class="popup-val">${plant.mw.toLocaleString()} MW</span></div>
      <div class="popup-row"><span class="popup-label">Country</span><span class="popup-val">${escapeHtml(plant.c)}</span></div>
      <div class="popup-row"><span class="popup-label">Confidence</span><span class="popup-val">Source-native precision</span></div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "300px", offset: 10 })
    .setLngLat([plant.lon, plant.lat])
    .setHTML(html)
    .addTo(m);
}

function showDCPopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, dc: Asset, event?: MouseEvent | PointerEvent) {
  if (popupRef.current) popupRef.current.remove();
  if (!("op" in dc)) return;
  const html = `
    <div class="popup-content">
      <div class="popup-header">${escapeHtml(dc.n)}</div>
      <div class="popup-row"><span class="popup-label">Type</span><span class="popup-val">Data Center</span></div>
      <div class="popup-row"><span class="popup-label">Owner</span><span class="popup-val">${escapeHtml(dc.op || "N/A")}</span></div>
      <div class="popup-row"><span class="popup-label">Country</span><span class="popup-val">${escapeHtml(dc.c)}</span></div>
      <div class="popup-row"><span class="popup-label">Capacity</span><span class="popup-val">${dc.mw ? dc.mw.toLocaleString() + " MW" : "N/A"}</span></div>
      <div class="popup-row"><span class="popup-label">Precision</span><span class="popup-val">${dc.coordinate_precision || "N/A"}</span></div>
      <div class="popup-row"><span class="popup-label">Confidence</span><span class="popup-val">${dc.confidence ?? "N/A"}</span></div>
      <div class="popup-note">Metro-level coordinates — not exact facility location</div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "300px", offset: 10 })
    .setLngLat([dc.lon, dc.lat])
    .setHTML(html)
    .addTo(m);
}

function showCablePopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, cable: Asset, lngLat: maplibregl.LngLat, event?: MouseEvent | PointerEvent) {
  if (popupRef.current) popupRef.current.remove();
  const precision = "geometry_precision" in cable ? cable.geometry_precision : "N/A";
  const confidence = "confidence" in cable && cable.confidence ? cable.confidence : "N/A";
  const html = `
    <div class="popup-content">
      <div class="popup-header">${escapeHtml(cable.n)}</div>
      <div class="popup-row"><span class="popup-label">Type</span><span class="popup-val">Submarine Cable</span></div>
      <div class="popup-row"><span class="popup-label">Precision</span><span class="popup-val">${precision}</span></div>
      <div class="popup-row"><span class="popup-label">Confidence</span><span class="popup-val">${confidence}</span></div>
      <div class="popup-note">Generalized public geometry — not exact trench route</div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "300px", offset: 10 })
    .setLngLat(lngLat)
    .setHTML(html)
    .addTo(m);
}

function escapeHtml(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function applyFilters(m: maplibregl.Map, filters: FilterState) {
  const filtersArr: maplibregl.ExpressionSpecification[] = [];
  if (filters.fuelType) {
    filtersArr.push(["==", ["get", "f"], filters.fuelType]);
  }
  if (filters.country) {
    filtersArr.push(["in", filters.country, ["get", "c"]]);
  }
  if (filters.minMw > 0) {
    filtersArr.push([">=", ["get", "mw"], filters.minMw]);
  }

  if (filtersArr.length > 0) {
    m.setFilter(LAYER_IDS.POWER_PLANTS, ["all" as never, ...filtersArr] as unknown as maplibregl.FilterSpecification);
  } else {
    m.setFilter(LAYER_IDS.POWER_PLANTS, ["!", ["has", "point_count"]]);
  }
}
