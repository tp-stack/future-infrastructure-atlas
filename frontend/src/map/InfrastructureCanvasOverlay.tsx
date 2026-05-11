import { useRef, useEffect, useCallback } from "react";
import type maplibregl from "maplibre-gl";
import type { AtlasData, FilterState, PowerPlant, Cable, DataCenter } from "./types";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  mapInstance: maplibregl.Map | null;
  mapLoaded: boolean;
  showTestPoints?: boolean;
  onCanvasDiagnostics?: (d: CanvasDiagnostics) => void;
  onCanvasClick?: (asset: AssetHit | null) => void;
}

export interface CanvasDiagnostics {
  active: boolean;
  canvasWidth: number;
  canvasHeight: number;
  powerPlantsDrawn: number;
  cableLinesDrawn: number;
  dataCentersDrawn: number;
  testPointsDrawn: number;
  lastDrawTime: string;
  lastError: string | null;
  usingFallbackProjection: boolean;
}

export interface AssetHit {
  type: "power_plant" | "data_center";
  asset: PowerPlant | DataCenter;
  x: number;
  y: number;
}

const GRID_COLOR = "rgba(60, 60, 70, 0.3)";
const GRID_LINE_WIDTH = 0.5;
const EQUATOR_COLOR = "rgba(80, 80, 90, 0.6)";
const EQUATOR_LINE_WIDTH = 1;

const FUEL_COLORS: Record<string, string> = {
  Hydro: "#4fc3f7",
  Solar: "#d69a13",
  Wind: "#5cb88a",
  Nuclear: "#a87bc7",
  Coal: "#d45050",
  "Natural Gas": "#d4956a",
  Oil: "#c47555",
  Biomass: "#7ab87a",
  Geothermal: "#d48a6a",
  Waste: "#8a8a8a",
  Cogeneration: "#6a9fd4",
  "Wave and Tidal": "#4dd0e1",
};

const OTHER_COLOR = "#8d93a1";

const TEST_POINTS = [
  { n: "New York", lat: 40.7128, lon: -74.006, color: "#ff4444" },
  { n: "London", lat: 51.5074, lon: -0.1278, color: "#44ff44" },
  { n: "Singapore", lat: 1.3521, lon: 103.8198, color: "#4444ff" },
  { n: "Sydney", lat: -33.8688, lon: 151.2093, color: "#ffff44" },
  { n: "São Paulo", lat: -23.5505, lon: -46.6333, color: "#ff44ff" },
];

function mercY(lat: number): number {
  return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
}

export default function InfrastructureCanvasOverlay({
  data,
  filters,
  visibleLayers,
  mapInstance,
  mapLoaded,
  showTestPoints,
  onCanvasDiagnostics,
  onCanvasClick,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const animFrameRef = useRef(0);
  const resizeObsRef = useRef<ResizeObserver | null>(null);
  const diagRef = useRef<CanvasDiagnostics>({
    active: false,
    canvasWidth: 0,
    canvasHeight: 0,
    powerPlantsDrawn: 0,
    cableLinesDrawn: 0,
    dataCentersDrawn: 0,
    testPointsDrawn: 0,
    lastDrawTime: "",
    lastError: null,
    usingFallbackProjection: true,
  });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const container = containerRef.current;
    if (!container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    try {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const cssW = rect.width;
      const cssH = rect.height;
      if (cssW < 1 || cssH < 1) return;

      if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
        canvas.width = Math.floor(cssW * dpr);
        canvas.height = Math.floor(cssH * dpr);
        canvas.style.width = `${cssW}px`;
        canvas.style.height = `${cssH}px`;
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      ctx.clearRect(0, 0, cssW, cssH);

      const map = mapInstance;
      const usingFallback = !map || !mapLoaded;
      const center: [number, number] = map && mapLoaded
        ? [map.getCenter().lng, map.getCenter().lat]
        : [10, 30];
      const zoom: number = map && mapLoaded ? map.getZoom() : 1.8;

      function project(lon: number, lat: number): [number, number] {
        if (map && mapLoaded) {
          try {
            const p = map.project([lon, lat]);
            return [p.x, p.y];
          } catch {
          }
        }
        const scaleFactor = cssH / (2 * Math.PI) * Math.pow(2, zoom - 1) * 0.4;
        const x = cssW / 2 + (lon - center[0]) * scaleFactor * Math.cos(center[1] * Math.PI / 180);
        const mc = mercY(center[1]);
        const y = cssH / 2 - (mercY(lat) - mc) * scaleFactor;
        return [x, y];
      }

      let diag: CanvasDiagnostics = {
        active: true,
        canvasWidth: cssW,
        canvasHeight: cssH,
        powerPlantsDrawn: 0,
        cableLinesDrawn: 0,
        dataCentersDrawn: 0,
        testPointsDrawn: 0,
        lastDrawTime: new Date().toISOString(),
        lastError: null,
        usingFallbackProjection: usingFallback,
      };

      // --- Graticule ---
      drawGraticule(ctx, cssW, cssH, project);

      // --- Power Plants ---
      if (visibleLayers.power_plants) {
        const filtered = filterPlants(data.power_plants, filters);
        const grouped = groupByFuel(filtered);
        const isLowZoom = zoom < 4;
        const pointRadius = isLowZoom ? 1.2 : Math.min(3, 1 + (zoom - 4) * 0.3);

        for (const fuel of Object.keys(grouped)) {
          const color = FUEL_COLORS[fuel] || OTHER_COLOR;
          const plants = grouped[fuel];
          ctx.fillStyle = color;
          const opacity = isLowZoom ? 0.6 : Math.min(0.85, 0.5 + zoom * 0.03);
          ctx.globalAlpha = opacity;

          for (const p of plants) {
            const [x, y] = project(p.lon, p.lat);
            if (x < -10 || x > cssW + 10 || y < -10 || y > cssH + 10) continue;
            ctx.beginPath();
            ctx.arc(x, y, pointRadius, 0, Math.PI * 2);
            ctx.fill();
            diag.powerPlantsDrawn++;
          }
        }
        ctx.globalAlpha = 1;
      }

      // --- Cables ---
      if (visibleLayers.cables) {
        const mappedCables = data.cables.filter(
          (c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length >= 2
        );
        ctx.strokeStyle = "#4cc9e8";
        ctx.lineWidth = Math.max(1.5, Math.min(3, 1 + zoom * 0.15));
        ctx.globalAlpha = 0.8;
        for (const c of mappedCables) {
          if (!c.geometry || c.geometry.length < 2) continue;
          ctx.beginPath();
          let started = false;
          let segmentsVisible = 0;
          for (const coord of c.geometry) {
            const [x, y] = project(coord[0], coord[1]);
            if (x < -100 || x > cssW + 100 || y < -100 || y > cssH + 100) {
              started = false;
              continue;
            }
            if (!started) {
              ctx.moveTo(x, y);
              started = true;
            } else {
              ctx.lineTo(x, y);
            }
            segmentsVisible++;
          }
          if (segmentsVisible >= 2) {
            ctx.stroke();
            diag.cableLinesDrawn++;
          }
        }
        ctx.globalAlpha = 1;
      }

      // --- Data Centers ---
      if (visibleLayers.data_centers) {
        const mappedDCs = data.data_centers.filter(
          (d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null
        );
        const dcRadius = Math.max(4, Math.min(8, 4 + zoom * 0.5));
        for (const d of mappedDCs) {
          const [x, y] = project(d.lon!, d.lat!);
          if (x < -20 || x > cssW + 20 || y < -20 || y > cssH + 20) continue;
          ctx.beginPath();
          ctx.arc(x, y, dcRadius, 0, Math.PI * 2);
          ctx.fillStyle = "#e8e5dc";
          ctx.globalAlpha = 0.9;
          ctx.fill();
          ctx.strokeStyle = "#4cc9e8";
          ctx.lineWidth = 1.5;
          ctx.globalAlpha = 0.8;
          ctx.stroke();
          diag.dataCentersDrawn++;
        }
        ctx.globalAlpha = 1;
      }

      // --- Test Points ---
      if (showTestPoints) {
        const tpRadius = Math.max(5, 8 * Math.pow(2, zoom - 2) / 60);
        for (const tp of TEST_POINTS) {
          const [x, y] = project(tp.lon, tp.lat);
          if (x < -20 || x > cssW + 20 || y < -20 || y > cssH + 20) continue;
          ctx.beginPath();
          ctx.arc(x, y, tpRadius, 0, Math.PI * 2);
          ctx.fillStyle = tp.color;
          ctx.globalAlpha = 0.9;
          ctx.fill();
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.fillStyle = "#ffffff";
          ctx.font = "10px sans-serif";
          ctx.fillText(tp.n, x + tpRadius + 4, y + 4);
          diag.testPointsDrawn++;
        }
      }

      diagRef.current = diag;
      onCanvasDiagnostics?.(diag);
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      console.error("[CanvasOverlay] Draw error:", errMsg);
      diagRef.current.lastError = errMsg;
      onCanvasDiagnostics?.(diagRef.current);
    }
  }, [data, filters, visibleLayers, mapInstance, mapLoaded, showTestPoints, onCanvasDiagnostics]);

  // Trigger redraw when any dependency changes
  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [draw]);

  // Set up resize observer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    containerRef.current = parent as HTMLDivElement;

    resizeObsRef.current = new ResizeObserver(() => {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = requestAnimationFrame(draw);
    });
    resizeObsRef.current.observe(parent);

    return () => {
      resizeObsRef.current?.disconnect();
    };
  }, [draw]);

  // Listen for map move/zoom events
  useEffect(() => {
    if (!mapInstance || !mapLoaded) return;
    const onMove = () => {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = requestAnimationFrame(draw);
    };
    mapInstance.on("move", onMove);
    mapInstance.on("resize", onMove);
    return () => {
      mapInstance.off("move", onMove);
      mapInstance.off("resize", onMove);
    };
  }, [mapInstance, mapLoaded, draw]);

  // Click handling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !onCanvasClick) return;
    const handleClick = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const map = mapInstance;
      const isLoaded = map && mapLoaded;

      function project(lon: number, lat: number): [number, number] {
        if (isLoaded) {
          try { const p = map!.project([lon, lat]); return [p.x, p.y]; } catch {}
        }
        return [mx + 9999, my + 9999];
      }

      const searchRadius = 10;
      let bestDist = searchRadius;
      let bestHit: AssetHit | null = null;

      if (visibleLayers.power_plants) {
        const filtered = filterPlants(data.power_plants, filters);
        for (const p of filtered) {
          const [px, py] = project(p.lon, p.lat);
          const d = Math.hypot(px - mx, py - my);
          if (d < bestDist) {
            bestDist = d;
            bestHit = { type: "power_plant", asset: p, x: px, y: py };
          }
        }
      }

      if (visibleLayers.data_centers && !bestHit) {
        const mappedDCs = data.data_centers.filter(
          (d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null
        );
        for (const d of mappedDCs) {
          const [px, py] = project(d.lon!, d.lat!);
          const dist = Math.hypot(px - mx, py - my);
          if (dist < bestDist) {
            bestDist = dist;
            bestHit = { type: "data_center", asset: d, x: px, y: py };
          }
        }
      }

      onCanvasClick(bestHit);
    };
    canvas.addEventListener("click", handleClick);
    return () => canvas.removeEventListener("click", handleClick);
  }, [data, filters, visibleLayers, mapInstance, mapLoaded, onCanvasClick]);

  return <canvas ref={canvasRef} className="infrastructure-canvas" />;
}

function drawGraticule(ctx: CanvasRenderingContext2D, w: number, h: number, project: (lon: number, lat: number) => [number, number]) {
  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = GRID_LINE_WIDTH;
  ctx.globalAlpha = 1;

  for (let lon = -180; lon <= 180; lon += 30) {
    const [x] = project(lon, 0);
    if (x < -5 || x > w + 5) continue;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  for (let lat = -90; lat <= 90; lat += 30) {
    const [, y] = project(0, lat);
    if (y < -5 || y > h + 5) continue;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  ctx.strokeStyle = EQUATOR_COLOR;
  ctx.lineWidth = EQUATOR_LINE_WIDTH;
  const [, eqY] = project(0, 0);
  if (eqY >= 0 && eqY <= h) {
    ctx.beginPath();
    ctx.moveTo(0, eqY);
    ctx.lineTo(w, eqY);
    ctx.stroke();
  }

  const [pmX] = project(0, 0);
  if (pmX >= 0 && pmX <= w) {
    ctx.beginPath();
    ctx.moveTo(pmX, 0);
    ctx.lineTo(pmX, h);
    ctx.stroke();
  }
}

function filterPlants(plants: PowerPlant[], filters: FilterState): PowerPlant[] {
  return plants.filter((p) => {
    if (p.lat == null || p.lon == null) return false;
    if (filters.fuelType && p.f !== filters.fuelType) return false;
    if (filters.country && p.c !== filters.country) return false;
    if (filters.minMw > 0 && p.mw < filters.minMw) return false;
    return true;
  });
}

function groupByFuel(plants: PowerPlant[]): Record<string, PowerPlant[]> {
  const groups: Record<string, PowerPlant[]> = {};
  for (const p of plants) {
    const fuel = p.f || "Other";
    if (!groups[fuel]) groups[fuel] = [];
    groups[fuel].push(p);
  }
  return groups;
}
