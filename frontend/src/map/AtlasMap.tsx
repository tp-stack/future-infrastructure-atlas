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
}

const DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  name: "Dark Atlas",
  sources: {
    "osm-tiles": {
      type: "raster",
      tiles: ["https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"],
      tileSize: 256,
      attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>',
    },
  },
  layers: [
    {
      id: "background",
      type: "background" as const,
      paint: { "background-color": "#0a0a0f" },
    },
    {
      id: "osm-tiles-layer",
      type: "raster" as const,
      source: "osm-tiles",
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

export default function AtlasMap({ data, filters, visibleLayers, onPopup }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [loaded, setLoaded] = useState(false);

  const initMap = useCallback(() => {
    if (!mapContainer.current || map.current) return;
    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: DARK_STYLE,
      center: [10, 30],
      zoom: 1.5,
    });
    m.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.current = m;

    m.on("load", () => {
      addPowerPlantLayer(m, data.power_plants);
      addCableLayer(m, data.cables);
      addDataCenterLayer(m, data.data_centers);
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
      showPopup(m, popupRef, plant);
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
      showDCPopup(m, popupRef, dc);
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
      showCablePopup(m, popupRef, cable, e.lngLat);
      onPopup(cable);
    });

    m.on("mouseenter", [LAYER_IDS.POWER_CLUSTERS, LAYER_IDS.POWER_PLANTS, LAYER_IDS.DATA_CENTERS, LAYER_IDS.CABLES], () => {
      m.getCanvas().style.cursor = "pointer";
    });
    m.on("mouseleave", [LAYER_IDS.POWER_CLUSTERS, LAYER_IDS.POWER_PLANTS, LAYER_IDS.DATA_CENTERS, LAYER_IDS.CABLES], () => {
      m.getCanvas().style.cursor = "";
    });
  }, [data, onPopup]);

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

  return <div ref={mapContainer} className="map-container" />;
}

function addPowerPlantLayer(m: maplibregl.Map, plants: PowerPlant[]) {
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: plants.map((p) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] },
      properties: { n: p.n, c: p.c, f: p.f, mw: p.mw },
    })),
  };

  m.addSource(LAYER_IDS.POWER_PLANTS, {
    type: "geojson",
    data: geojson,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 50,
  });

  m.addLayer({
    id: LAYER_IDS.POWER_CLUSTERS,
    type: "circle",
    source: LAYER_IDS.POWER_PLANTS,
    filter: ["has", "point_count"],
    paint: CLUSTER_PAINT as unknown as maplibregl.CircleLayerSpecification["paint"],
  });

  m.addLayer({
    id: LAYER_IDS.POWER_CLUSTER_COUNT,
    type: "symbol",
    source: LAYER_IDS.POWER_PLANTS,
    filter: ["has", "point_count"],
    layout: CLUSTER_COUNT_PAINT as unknown as maplibregl.SymbolLayerSpecification["layout"],
    paint: {},
  });

  m.addLayer({
    id: LAYER_IDS.POWER_PLANTS,
    type: "circle",
    source: LAYER_IDS.POWER_PLANTS,
    filter: ["!", ["has", "point_count"]],
    paint: POWER_PAINT as unknown as maplibregl.CircleLayerSpecification["paint"],
  });
}

function addCableLayer(m: maplibregl.Map, cables: { n: string; source: string; geometry: number[][]; mapped_status?: string; geometry_precision?: string; confidence?: number; operators?: string; landing_points?: string; length_km?: string }[]) {
  const withGeom = cables.filter((c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length >= 2);
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: withGeom.map((c) => ({
      type: "Feature" as const,
      geometry: { type: "LineString" as const, coordinates: c.geometry },
      properties: { n: c.n, source: c.source, mapped_status: c.mapped_status, geometry_precision: c.geometry_precision, confidence: c.confidence },
    })),
  };
  m.addSource(LAYER_IDS.CABLES, { type: "geojson", data: geojson });
  m.addLayer({
    id: LAYER_IDS.CABLES,
    type: "line",
    source: LAYER_IDS.CABLES,
    paint: CABLE_PAINT as unknown as maplibregl.LineLayerSpecification["paint"],
    layout: { visibility: "none" as const },
  });
}

function addDataCenterLayer(m: maplibregl.Map, dcs: { n: string; op: string; c: string; city: string; lat: number; lon: number; mw: number | null; source: string; mapped_status?: string; coordinate_precision?: string; confidence?: number }[]) {
  const withCoords = dcs.filter((d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null);
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: withCoords.map((d) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [d.lon, d.lat] },
      properties: { n: d.n, op: d.op, c: d.c, city: d.city, mw: d.mw, source: d.source, mapped_status: d.mapped_status, coordinate_precision: d.coordinate_precision, confidence: d.confidence },
    })),
  };
  m.addSource(LAYER_IDS.DATA_CENTERS, { type: "geojson", data: geojson });
  m.addLayer({
    id: LAYER_IDS.DATA_CENTERS,
    type: "circle",
    source: LAYER_IDS.DATA_CENTERS,
    paint: DATA_CENTER_PAINT as unknown as maplibregl.CircleLayerSpecification["paint"],
    layout: { visibility: "none" as const },
  });
}

function showPopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, asset: Asset) {
  if (popupRef.current) popupRef.current.remove();
  if ("f" in asset) {
    const plant = asset;
    const html = `
      <div class="popup-content">
        <h3>${escapeHtml(plant.n)}</h3>
        <div><span class="label">Type</span> Power Plant</div>
        <div><span class="label">Fuel</span> ${escapeHtml(plant.f)}</div>
        <div><span class="label">Capacity</span> ${plant.mw.toLocaleString()} MW</div>
        <div><span class="label">Country</span> ${escapeHtml(plant.c)}</div>
      </div>
    `;
    popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "280px" })
      .setLngLat([plant.lon, plant.lat])
      .setHTML(html)
      .addTo(m);
  } else {
    showGenericPopup(m, popupRef, asset);
  }
}

function showDCPopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, dc: Asset) {
  if (popupRef.current) popupRef.current.remove();
  if (!("op" in dc)) return;
  const html = `
    <div class="popup-content">
      <h3>${escapeHtml(dc.n)}</h3>
      <div><span class="label">Type</span> Data Center</div>
      <div><span class="label">Owner</span> ${escapeHtml(dc.op)}</div>
      <div><span class="label">Country</span> ${escapeHtml(dc.c)}</div>
      <div><span class="label">Capacity</span> ${dc.mw ? dc.mw.toLocaleString() + " MW" : "N/A"}</div>
      <div><span class="label">Precision</span> ${dc.coordinate_precision || ""}</div>
      <div><span class="label">Confidence</span> ${dc.confidence ?? "N/A"}</div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "280px" })
    .setLngLat([dc.lon, dc.lat])
    .setHTML(html)
    .addTo(m);
}

function showCablePopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, cable: Asset, lngLat: maplibregl.LngLat) {
  if (popupRef.current) popupRef.current.remove();
  const html = `
    <div class="popup-content">
      <h3>${escapeHtml(cable.n)}</h3>
      <div><span class="label">Type</span> Submarine Cable</div>
      <div><span class="label">Precision</span> ${"geometry_precision" in cable ? cable.geometry_precision : ""}</div>
      <div><span class="label">Confidence</span> ${"confidence" in cable && cable.confidence ? cable.confidence : "N/A"}</div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "280px" })
    .setLngLat(lngLat)
    .setHTML(html)
    .addTo(m);
}

function showGenericPopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, asset: Asset) {
  if (popupRef.current) popupRef.current.remove();
  const status = asset.mapped_status ?? "mapped";
  const html = `
    <div class="popup-content">
      <h3>${escapeHtml(asset.n)}</h3>
      <div><span class="label">Status</span> ${status}</div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "280px" })
    .setLngLat([0, 0])
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
