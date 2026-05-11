import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, PowerPlant } from "./types";
import { LAYER_IDS, POWER_PAINT, DATA_CENTER_PAINT, CABLE_PAINT, CLUSTER_PAINT, CLUSTER_COUNT_PAINT } from "./layers";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  onPopup: (plant: PowerPlant | null) => void;
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
      addDataCenterLayer(m, data.data_centers, data.metadata);
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
      const plant: PowerPlant = {
        n: (props.n as string) || "",
        c: (props.c as string) || "",
        f: (props.f as string) || "",
        mw: (props.mw as number) || 0,
        lat: coords[1],
        lon: coords[0],
      };
      showPopup(m, popupRef, plant);
      onPopup(plant);
    });

    m.on("mouseenter", [LAYER_IDS.POWER_CLUSTERS, LAYER_IDS.POWER_PLANTS], () => {
      m.getCanvas().style.cursor = "pointer";
    });
    m.on("mouseleave", [LAYER_IDS.POWER_CLUSTERS, LAYER_IDS.POWER_PLANTS], () => {
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

function addCableLayer(m: maplibregl.Map, cables: { n: string; source: string; geometry: number[][] }[]) {
  const withGeom = cables.filter((c) => c.geometry && c.geometry.length >= 2);
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: withGeom.map((c) => ({
      type: "Feature" as const,
      geometry: { type: "LineString" as const, coordinates: c.geometry },
      properties: { n: c.n, source: c.source },
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

function addDataCenterLayer(m: maplibregl.Map, dcs: { n: string; lat: number; lon: number }[], metadata: { counts: { data_centers_mapped: number } }) {
  const withCoords = dcs.filter((d) => d.lat != null && d.lon != null);
  const geojson: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: withCoords.map((d) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [d.lon, d.lat] },
      properties: { n: d.n },
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

function showPopup(m: maplibregl.Map, popupRef: React.MutableRefObject<maplibregl.Popup | null>, plant: PowerPlant) {
  if (popupRef.current) popupRef.current.remove();
  const html = `
    <div class="popup-content">
      <h3>${escapeHtml(plant.n)}</h3>
      <div><span class="label">Fuel</span> ${escapeHtml(plant.f)}</div>
      <div><span class="label">Capacity</span> ${plant.mw.toLocaleString()} MW</div>
      <div><span class="label">Country</span> ${escapeHtml(plant.c)}</div>
    </div>
  `;
  popupRef.current = new maplibregl.Popup({ closeButton: true, maxWidth: "280px" })
    .setLngLat([plant.lon, plant.lat])
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
