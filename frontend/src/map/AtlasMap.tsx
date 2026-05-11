import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AtlasData, FilterState, Asset } from "./types";
import InfrastructureCanvasOverlay from "./InfrastructureCanvasOverlay";
import type { CanvasDiagnostics } from "./InfrastructureCanvasOverlay";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  onPopup: (asset: Asset | null) => void;
  onCanvasDiagnostics?: (d: CanvasDiagnostics) => void;
  showTestPoints?: boolean;
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
    { id: "background", type: "background" as const, paint: { "background-color": DARK_BG } },
    { id: "basemap-dark-layer", type: "raster" as const, source: "basemap-dark", minzoom: 0, maxzoom: 20 },
  ],
};

export default function AtlasMap({ data, filters, visibleLayers, onPopup, onCanvasDiagnostics, showTestPoints }: Props) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);

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
  }, []);

  useEffect(() => {
    initMap();
    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [initMap]);

  const handleResetView = useCallback(() => {
    if (!map.current) return;
    map.current.flyTo({ center: [10, 30], zoom: 1.8 });
  }, []);

  const handleFitData = useCallback(() => {
    if (!map.current) return;
    const bounds = new maplibregl.LngLatBounds();
    let hasData = false;
    for (const p of data.power_plants) { bounds.extend([p.lon, p.lat]); hasData = true; }
    for (const d of data.data_centers) { if (d.lat != null && d.lon != null) { bounds.extend([d.lon, d.lat]); hasData = true; } }
    if (hasData) map.current.fitBounds(bounds, { padding: 60, maxZoom: 10 });
  }, [data]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="map-canvas" />
      <InfrastructureCanvasOverlay
        data={data}
        filters={filters}
        visibleLayers={visibleLayers}
        showTestPoints={showTestPoints}
        onCanvasDiagnostics={onCanvasDiagnostics}
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
