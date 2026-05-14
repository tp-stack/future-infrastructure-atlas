import { useRef, useEffect, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { registerPMTilesProtocol, getPMTilesSources, getPMTilesLayers, type TileStatus } from "./pmtiles";
import { getLightTopoLayers, getLightTopoSources, MAPLIBRE_GLYPHS_URL } from "./basemaps";
import type { AtlasCore } from "./types";

interface Props {
  core: AtlasCore;
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

function getTileStatusFromCore(core: AtlasCore): TileStatus {
  const reg = core.tile_registry || {};
  return {
    power_plants: reg.power_plants?.status?.startsWith("present") ? "present" : "missing",
    submarine_cables: reg.submarine_cables?.status?.startsWith("present") ? "present" : "missing",
    data_centers: reg.data_centers?.status?.startsWith("present") ? "present" : "missing",
  };
}

interface LayerToggle {
  key: string;
  label: string;
  visible: boolean;
}

export default function PMTilesAtlasMap({ core }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [status, setStatus] = useState({
    mapLoaded: false,
    graticuleAdded: false,
    tilesAdded: false,
    zoom: 0,
    center: "",
    error: null as string | null,
  });
  const [toggles, setToggles] = useState<LayerToggle[]>([
    { key: "power_plants", label: "Power Plants", visible: true },
    { key: "cables", label: "Submarine Cables", visible: true },
    { key: "data_centers", label: "Data Centers", visible: true },
  ]);
  const [debugVisible, setDebugVisible] = useState(true);

  const tileStatus = getTileStatusFromCore(core);
  const anyTilesPresent = tileStatus.power_plants === "present" || tileStatus.submarine_cables === "present" || tileStatus.data_centers === "present";

  const visibleLayers = {
    power_plants: toggles.find((t) => t.key === "power_plants")?.visible ?? true,
    cables: toggles.find((t) => t.key === "cables")?.visible ?? true,
    data_centers: toggles.find((t) => t.key === "data_centers")?.visible ?? true,
  };

  const handleToggle = useCallback((key: string) => {
    setToggles((prev) => prev.map((t) => (t.key === key ? { ...t, visible: !t.visible } : t)));
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    registerPMTilesProtocol();

    const tileSources = getPMTilesSources(tileStatus);
    const hasSources = Object.keys(tileSources).length > 0;

    const style: maplibregl.StyleSpecification = {
      version: 8,
      name: "PMTiles Atlas",
      glyphs: MAPLIBRE_GLYPHS_URL,
      sources: {
        ...getLightTopoSources(),
        ...tileSources,
      },
      layers: getLightTopoLayers(),
    };

    const m = new maplibregl.Map({
      container: containerRef.current,
      style,
      center: [10, 20],
      zoom: 1.35,
      renderWorldCopies: false,
    });

    m.addControl(new maplibregl.NavigationControl(), "top-right");

    m.on("load", () => {
      m.resize();

      setStatus((s) => ({ ...s, mapLoaded: true }));

      const graticuleFC = buildGraticule();
      m.addSource("graticule-source", { type: "geojson", data: graticuleFC });
      m.addLayer({
        id: "graticule-lines",
        type: "line",
        source: "graticule-source",
        paint: { "line-color": "rgba(80,90,100,0.18)", "line-width": 0.5 },
      });
      setStatus((s) => ({ ...s, graticuleAdded: true }));

      if (hasSources) {
        const tileLayers = getPMTilesLayers(tileStatus, visibleLayers);
        for (const layer of tileLayers) {
          m.addLayer(layer);
        }
        setStatus((s) => ({ ...s, tilesAdded: true }));
      }

      m.fitBounds([[-180, -60], [180, 85]], { padding: 20, maxZoom: 2.5, duration: 0 });

      m.on("move", () => {
        const z = m.getZoom();
        const c = m.getCenter();
        setStatus((s) => ({ ...s, zoom: z, center: `${c.lat.toFixed(2)}, ${c.lng.toFixed(2)}` }));
      });

      const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true });
      const getInteractiveTileLayers = () => (
        ["power_plants_tiles-layer", "submarine_cables_tiles-layer", "data_centers_tiles-layer"]
          .filter((id) => m.getLayer(id))
      );

      m.on("click", (e: maplibregl.MapMouseEvent) => {
        const layers = getInteractiveTileLayers();
        if (layers.length === 0) return;
        const features = m.queryRenderedFeatures(e.point, { layers });
        if (!features || features.length === 0) return;

        const feat = features[0];
        const props = feat.properties as Record<string, unknown>;
        const lines: string[] = [`Name: ${props.n || props.name || "Unknown"}`];

        if (props.f) lines.push(`Fuel: ${props.f}`);
        if (props.mw) lines.push(`Capacity: ${props.mw} MW`);
        if (props.fuel) lines.push(`Fuel: ${props.fuel}`);
        if (props.capacity_mw) lines.push(`Capacity: ${props.capacity_mw} MW`);
        if (props.op) lines.push(`Operator: ${props.op}`);
        if (props.c) lines.push(`Country: ${props.c}`);
        if (props.source) lines.push(`Source: ${props.source}`);
        if (props.source_license) lines.push(`License: ${props.source_license}`);

        popup
          .setLngLat(e.lngLat)
          .setHTML(`<div style="font-family:system-ui;font-size:12px;line-height:1.5;max-width:260px">${lines.map((l) => `<div>${l}</div>`).join("")}</div>`)
          .addTo(m);
      });

      m.on("mousemove", (e: maplibregl.MapMouseEvent) => {
        const interactiveLayers = getInteractiveTileLayers();
        if (interactiveLayers.length === 0) {
          m.getCanvas().style.cursor = "";
          return;
        }
        const features = m.queryRenderedFeatures(e.point, { layers: interactiveLayers });
        m.getCanvas().style.cursor = features && features.length > 0 ? "pointer" : "";
      });
    });

    mapRef.current = m;

    return () => { m.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !status.tilesAdded) return;
    const tileLayers = getPMTilesLayers(tileStatus, visibleLayers);
    // Get existing layer ids
    const existingLayers = m.getStyle().layers?.map((l) => l.id) || [];
    // Remove existing tile layers
    for (const id of ["power_plants_tiles-layer", "submarine_cables_tiles-layer", "data_centers_tiles-layer"]) {
      if (existingLayers.includes(id)) {
        try { m.removeLayer(id); } catch { /* */ }
      }
    }
    // Re-add with current visibility
    for (const layer of tileLayers) {
      try { m.addLayer(layer); } catch { /* */ }
    }
  }, [toggles, visibleLayers, status.tilesAdded, tileStatus]);

  const handleResetView = useCallback(() => {
    mapRef.current?.fitBounds([[-180, -60], [180, 85]], { padding: 20, maxZoom: 2.5, duration: 500 });
  }, []);

  const missingLayers: string[] = [];
  if (tileStatus.power_plants === "missing") missingLayers.push("power_plants.pmtiles");
  if (tileStatus.submarine_cables === "missing") missingLayers.push("submarine_cables.pmtiles");
  if (tileStatus.data_centers === "missing") missingLayers.push("data_centers.pmtiles");

  return (
    <div style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />

      {!anyTilesPresent && (
        <div style={{
          position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
          zIndex: 100, background: "rgba(0,0,0,0.9)", color: "#f4efe6",
          padding: "20px 24px", borderRadius: 8, maxWidth: 420,
          fontFamily: "system-ui", fontSize: 13, lineHeight: 1.6, textAlign: "center",
        }}>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>No PMTiles Found</div>
          <div style={{ color: "#9ca3af", marginBottom: 12 }}>
            Build PMTiles files to enable vector tile layers:
          </div>
          <div style={{ fontFamily: "monospace", fontSize: 11, color: "#d69a13", textAlign: "left", background: "rgba(255,255,255,0.05)", padding: "10px 14px", borderRadius: 4 }}>
            python scripts/build_web_map_data.py --max-public-mb 5<br />
            python scripts/build_pmtiles.py --all --max-public-mb 25
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: "#6a6a72" }}>
            The light topographic basemap is loaded. Build PMTiles to add infrastructure vector layers.
          </div>
        </div>
      )}

      {missingLayers.length > 0 && anyTilesPresent && (
        <div style={{
          position: "absolute", bottom: 60, left: "50%", transform: "translateX(-50%)",
          zIndex: 100, background: "rgba(200,100,0,0.85)", color: "#fff",
          padding: "8px 14px", borderRadius: 4,
          fontFamily: "system-ui", fontSize: 11, lineHeight: 1.4, textAlign: "center",
          maxWidth: 500, pointerEvents: "none",
        }}>
          Missing: {missingLayers.join(", ")}. Run <code style={{ background: "rgba(0,0,0,0.3)", padding: "1px 4px", borderRadius: 2 }}>python scripts/build_pmtiles.py --all</code>
        </div>
      )}

      <div style={{
        position: "absolute", top: 10, right: 50, zIndex: 100,
        display: "flex", flexDirection: "column", gap: 4,
      }}>
        {toggles.map((t) => (
          <label key={t.key} style={{
            background: "rgba(0,0,0,0.75)", color: "#f4efe6",
            padding: "4px 10px", borderRadius: 4, cursor: "pointer",
            fontFamily: "system-ui", fontSize: 11,
            display: "flex", alignItems: "center", gap: 6,
            userSelect: "none",
          }}>
            <input
              type="checkbox"
              checked={t.visible}
              onChange={() => handleToggle(t.key)}
              style={{ accentColor: "#4cc9e8", width: 11, height: 11 }}
            />
            {t.label}
          </label>
        ))}
      </div>

      <div style={{
        position: "absolute", bottom: 10, right: 10, zIndex: 100,
      }}>
        <button
          onClick={handleResetView}
          style={{
            background: "rgba(0,0,0,0.75)", color: "#f4efe6", border: "none",
            padding: "6px 12px", borderRadius: 4, cursor: "pointer",
            fontFamily: "system-ui", fontSize: 11,
          }}
          title="Reset global view"
        >
          Reset Global View
        </button>
      </div>

      <div style={{
        position: "absolute", bottom: 10, left: 10, zIndex: 100,
      }}>
        <button
          onClick={() => setDebugVisible((v) => !v)}
          style={{
            background: "rgba(0,0,0,0.75)", color: "#f4efe6", border: "none",
            padding: "6px 12px", borderRadius: 4, cursor: "pointer",
            fontFamily: "system-ui", fontSize: 11,
          }}
        >
          {debugVisible ? "Hide Debug" : "Show Debug"}
        </button>
      </div>

      {debugVisible && (
        <div style={{
          position: "absolute", top: 10, left: 10, zIndex: 100,
          background: "rgba(0,0,0,0.85)", color: "#f4efe6",
          padding: "10px 14px", borderRadius: 6,
          fontFamily: "monospace", fontSize: 11, lineHeight: 1.7,
          pointerEvents: "none", minWidth: 220,
        }}>
          <div style={{ fontWeight: 700, marginBottom: 4, fontSize: 12 }}>PMTiles ATLAS DEBUG</div>
          <div>Map loaded: {status.mapLoaded ? "YES" : "NO"}</div>
          <div>Graticule: {status.graticuleAdded ? "YES" : "NO"}</div>
          <div>Tiles: {status.tilesAdded ? "YES" : "NO"}</div>
          <div style={{ color: tileStatus.power_plants === "present" ? "#62c370" : "#d95c5c" }}>
            Power plants: {tileStatus.power_plants}
          </div>
          <div style={{ color: tileStatus.submarine_cables === "present" ? "#62c370" : "#d95c5c" }}>
            Cables: {tileStatus.submarine_cables}
          </div>
          <div style={{ color: tileStatus.data_centers === "present" ? "#62c370" : "#d95c5c" }}>
            Data centers: {tileStatus.data_centers}
          </div>
          <div>Zoom: {status.zoom.toFixed(2)}</div>
          <div>Center: {status.center}</div>
          <div style={{ marginTop: 4, fontSize: 10, color: "#6a6a72" }}>
            PMTiles mode - light topographic basemap
          </div>
        </div>
      )}
    </div>
  );
}
