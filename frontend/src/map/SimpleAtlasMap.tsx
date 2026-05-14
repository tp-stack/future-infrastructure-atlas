import { useRef, useEffect, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData } from "./types";
import { buildPowerPlantGeoJSON, buildDataCenterGeoJSON, buildCableGeoJSON } from "./geojson";
import { getLightTopoStyle } from "./basemaps";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR } from "./layers";

interface Props {
  data: AtlasData;
}

function buildGraticule(): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (let lon = -180; lon <= 180; lon += 30) {
    const coords: number[][] = [];
    for (let lat = -90; lat <= 90; lat += 5) coords.push([lon, lat]);
    features.push({ type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} });
  }
  for (let lat = -90; lat <= 90; lat += 30) {
    const coords: number[][] = [];
    for (let lon = -180; lon <= 180; lon += 5) coords.push([lon, lat]);
    features.push({ type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} });
  }
  return { type: "FeatureCollection", features };
}

function buildProofPoints(): GeoJSON.FeatureCollection {
  const pts = [
    { n: "London", lat: 51.5074, lon: -0.1278 },
    { n: "New York", lat: 40.7128, lon: -74.006 },
    { n: "Singapore", lat: 1.3521, lon: 103.8198 },
    { n: "Tokyo", lat: 35.6762, lon: 139.6503 },
    { n: "São Paulo", lat: -23.5505, lon: -46.6333 },
  ];
  return {
    type: "FeatureCollection",
    features: pts.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: { name: p.n },
    })),
  };
}

const BASE_STYLE: maplibregl.StyleSpecification = getLightTopoStyle("Simple Atlas Debug");

export default function SimpleAtlasMap({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [status, setStatus] = useState({
    mapLoaded: false,
    sourcesAdded: false,
    layersAdded: false,
    ppCount: 0,
    dcCount: 0,
    cableCount: 0,
    zoom: 0,
    center: "",
  });

  const params = new URLSearchParams(window.location.search);
  const showProof = params.get("proof") === "1";

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const m = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE,
      center: [10, 20],
      zoom: 1.35,
      renderWorldCopies: false,
    });

    m.addControl(new maplibregl.NavigationControl(), "top-right");

    m.on("load", () => {
      m.resize();

      const ppFC = buildPowerPlantGeoJSON(data, { fuelType: "", country: "", minMw: 0 });
      const dcFC = buildDataCenterGeoJSON(data, { fuelType: "", country: "", minMw: 0 });
      const cableFC = buildCableGeoJSON(data);
      const graticuleFC = buildGraticule();

      setStatus((s) => ({ ...s, ppCount: ppFC.features.length, dcCount: dcFC.features.length, cableCount: cableFC.features.length }));

      m.addSource("graticule-source", { type: "geojson", data: graticuleFC });

      m.addLayer({
        id: "graticule-lines",
        type: "line",
        source: "graticule-source",
        paint: { "line-color": "rgba(80,90,100,0.18)", "line-width": 0.5 },
      });

      m.addSource("power-plants-source", {
        type: "geojson",
        data: ppFC,
        cluster: true,
        clusterRadius: 40,
        clusterMaxZoom: 6,
      });

      m.addSource("data-centers-source", { type: "geojson", data: dcFC });
      m.addSource("submarine-cables-source", { type: "geojson", data: cableFC });

      m.addLayer({
        id: "submarine-cable-lines",
        type: "line",
        source: "submarine-cables-source",
        paint: { "line-color": CABLE_COLOR, "line-width": 2, "line-opacity": 0.85 },
      });

      m.addLayer({
        id: "power-clusters",
        type: "circle",
        source: "power-plants-source",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#f2b705",
          "circle-opacity": 0.9,
          "circle-radius": ["step", ["get", "point_count"], 18, 10, 24, 100, 32],
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
          "text-size": 11,
        },
        paint: { "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,0.5)", "text-halo-width": 1 },
      });

      m.addLayer({
        id: "power-points",
        type: "circle",
        source: "power-plants-source",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-radius": 4,
          "circle-color": "#f2b705",
          "circle-opacity": 0.9,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 0.5,
        },
      });

      m.addLayer({
        id: "data-center-points",
        type: "circle",
        source: "data-centers-source",
        paint: {
          "circle-radius": 7,
          "circle-color": DATA_CENTER_COLOR,
          "circle-opacity": 0.9,
          "circle-stroke-color": DATA_CENTER_STROKE_COLOR,
          "circle-stroke-width": 2,
        },
      });

      if (showProof) {
        m.addSource("proof-source", { type: "geojson", data: buildProofPoints() });
        m.addLayer({
          id: "proof-points",
          type: "circle",
          source: "proof-source",
          paint: {
            "circle-radius": 10,
            "circle-color": "#ff3333",
            "circle-opacity": 0.9,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 3,
          },
        });
      }

      setStatus((s) => ({ ...s, sourcesAdded: true, layersAdded: true, mapLoaded: true }));

      // Fit to data bounds
      const allCoords: [number, number][] = [];
      for (const f of ppFC.features) {
        const c = (f.geometry as GeoJSON.Point).coordinates;
        if (c[0] >= -180 && c[0] <= 180 && c[1] >= -90 && c[1] <= 90) allCoords.push([c[0], c[1]]);
      }
      for (const f of dcFC.features) {
        const c = (f.geometry as GeoJSON.Point).coordinates;
        if (c[0] >= -180 && c[0] <= 180 && c[1] >= -90 && c[1] <= 90) allCoords.push([c[0], c[1]]);
      }
      if (allCoords.length > 0) {
        let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
        for (const [lon, lat] of allCoords) {
          if (lon < minLon) minLon = lon;
          if (lon > maxLon) maxLon = lon;
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
        }
        m.fitBounds(
          [[Math.max(-180, minLon - 5), Math.max(-85, minLat - 5)], [Math.min(180, maxLon + 5), Math.min(85, maxLat + 5)]],
          { padding: 40, maxZoom: 2.5, duration: 0 },
        );
      }

      // Update status on move
      m.on("move", () => {
        const z = m.getZoom();
        const c = m.getCenter();
        setStatus((s) => ({ ...s, zoom: z, center: `${c.lat.toFixed(2)}, ${c.lng.toFixed(2)}` }));
      });

      // Simple popup on click
      m.on("click", (e: maplibregl.MapMouseEvent) => {
        const features = m.queryRenderedFeatures(e.point, {
          layers: ["power-points", "data-center-points", "submarine-cable-lines", "power-clusters", "proof-points"],
        });
        if (!features || features.length === 0) return;

        const feat = features[0];
        const layerId = feat.layer?.id;

        if (layerId === "power-clusters") {
          const clusterId = feat.properties?.cluster_id;
          (m.getSource("power-plants-source") as maplibregl.GeoJSONSource)
            .getClusterExpansionZoom(clusterId)
            .then((zoom: number) => {
              const geom = feat.geometry as GeoJSON.Point;
              m.easeTo({ center: [geom.coordinates[0], geom.coordinates[1]], zoom: Math.min(zoom + 1, 14) });
            });
          return;
        }

        const props = feat.properties as Record<string, unknown>;
        const lines = [`Name: ${props.name || "Unknown"}`];
        if (props.fuel) lines.push(`Fuel: ${props.fuel}`);
        if (props.capacity_mw) lines.push(`Capacity: ${props.capacity_mw} MW`);
        if ((props as Record<string, unknown>).operator) lines.push(`Operator: ${props.operator}`);
        if (props.country) lines.push(`Country: ${props.country}`);
        if (props.source) lines.push(`Source: ${props.source}`);

        new maplibregl.Popup({ closeButton: true, closeOnClick: true })
          .setLngLat(feat.geometry.type === "Point" ? (feat.geometry as GeoJSON.Point).coordinates as [number, number] : e.lngLat.toArray() as [number, number])
          .setHTML(`<div style="font-family:system-ui;font-size:12px;line-height:1.5;max-width:260px">${lines.map((l) => `<div>${l}</div>`).join("")}</div>`)
          .addTo(m);
      });

      // Cursor pointer
      const interactiveLayers = ["power-points", "data-center-points", "submarine-cable-lines", "proof-points"];
      m.on("mousemove", (e: maplibregl.MapMouseEvent) => {
        const features = m.queryRenderedFeatures(e.point, { layers: interactiveLayers });
        m.getCanvas().style.cursor = features && features.length > 0 ? "pointer" : "";
      });
    });

    mapRef.current = m;

    return () => { m.remove(); mapRef.current = null; };
  }, [data, showProof]);

  return (
    <div style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
      <div style={{
        position: "absolute", top: 10, left: 10, zIndex: 100,
        background: "rgba(0,0,0,0.85)", color: "#f4efe6",
        padding: "10px 14px", borderRadius: 6,
        fontFamily: "monospace", fontSize: 11, lineHeight: 1.7,
        pointerEvents: "none", minWidth: 200,
      }}>
        <div style={{ fontWeight: 700, marginBottom: 4, fontSize: 12 }}>SIMPLE ATLAS DEBUG</div>
        <div>Map loaded: {status.mapLoaded ? "YES" : "NO"}</div>
        <div>Sources added: {status.sourcesAdded ? "YES" : "NO"}</div>
        <div>Layers added: {status.layersAdded ? "YES" : "NO"}</div>
        <div>Power plant features: {status.ppCount.toLocaleString()}</div>
        <div>Data center features: {status.dcCount.toLocaleString()}</div>
        <div>Cable features: {status.cableCount.toLocaleString()}</div>
        <div>Zoom: {status.zoom.toFixed(2)}</div>
        <div>Center: {status.center}</div>
        {showProof && <div style={{ color: "#ff6b6b", fontWeight: 700 }}>PROOF POINTS ENABLED</div>}
        <div style={{ marginTop: 4, fontSize: 10, color: "#6a6a72" }}>
          {data.metadata.generated_at ? new Date(data.metadata.generated_at).toISOString().slice(0, 10) : ""}
        </div>
      </div>
    </div>
  );
}
