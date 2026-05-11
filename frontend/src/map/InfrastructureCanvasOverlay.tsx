import { useRef, useEffect, useCallback } from "react";
import type { AtlasData, FilterState, PowerPlant, Cable, DataCenter } from "./types";

interface Props {
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  mapInstance?: unknown;
  mapLoaded?: boolean;
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
  recordsReceived: number;
  validCoords: number;
  lastDrawTime: string;
  lastError: string | null;
  projectionMode: string;
}

export interface AssetHit {
  type: "power_plant" | "data_center";
  asset: PowerPlant | DataCenter;
  x: number;
  y: number;
}

const FUEL_COLORS: Record<string, string> = {
  Hydro: "#4cc9f0",
  Solar: "#f2b705",
  Wind: "#62c370",
  "Natural Gas": "#d99a6c",
  Nuclear: "#b985d6",
  Coal: "#d95c5c",
  Oil: "#c97955",
  Biomass: "#7ab87a",
  Geothermal: "#d48a6a",
  Waste: "#8a8a8a",
  Cogeneration: "#6a9fd4",
  "Wave and Tidal": "#4dd0e1",
};

const OTHER_COLOR = "#9ca3af";

const TEST_POINTS = [
  { n: "New York", lat: 40.7128, lon: -74.006, color: "#ff4444" },
  { n: "London", lat: 51.5074, lon: -0.1278, color: "#44ff44" },
  { n: "Singapore", lat: 1.3521, lon: 103.8198, color: "#4444ff" },
  { n: "Sydney", lat: -33.8688, lon: 151.2093, color: "#ffff44" },
  { n: "São Paulo", lat: -23.5505, lon: -46.6333, color: "#ff44ff" },
];

function getLon(record: Record<string, unknown>): number | null {
  const v = record.lon ?? record.longitude ?? record.lng ?? null;
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  return isFinite(n) ? n : null;
}

function getLat(record: Record<string, unknown>): number | null {
  const v = record.lat ?? record.latitude ?? null;
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  return isFinite(n) ? n : null;
}

function isValidLonLat(lon: number, lat: number): boolean {
  return isFinite(lon) && isFinite(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90;
}

function projectEquirectangular(lon: number, lat: number, w: number, h: number): [number, number] {
  const x = ((lon + 180) / 360) * w;
  const y = ((90 - lat) / 180) * h;
  return [x, y];
}

export default function InfrastructureCanvasOverlay({
  data,
  filters,
  visibleLayers,
  showTestPoints,
  onCanvasDiagnostics,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const animFrameRef = useRef(0);
  const resizeObsRef = useRef<ResizeObserver | null>(null);

  // Console-diagnose the first render
  console.log("[CanvasOverlay] Mounted. Plants:", data?.power_plants?.length);
  if (data?.power_plants?.length) {
    const first = data.power_plants[0];
    const lon = getLon(first as unknown as Record<string, unknown>);
    const lat = getLat(first as unknown as Record<string, unknown>);
    console.log("[CanvasOverlay] First plant:", first.n, "lon=", first.lon, "lat=", first.lat, "parsedLon=", lon, "parsedLat=", lat);
  }

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

      if (cssW < 1 || cssH < 1) {
        console.log("[CanvasOverlay] Canvas too small:", cssW, cssH);
        return;
      }

      if (canvas.width !== Math.floor(cssW * dpr) || canvas.height !== Math.floor(cssH * dpr)) {
        canvas.width = Math.floor(cssW * dpr);
        canvas.height = Math.floor(cssH * dpr);
        canvas.style.width = `${cssW}px`;
        canvas.style.height = `${cssH}px`;
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cssW, cssH);

      console.log("[CanvasOverlay] Drawing. Canvas:", cssW, "x", cssH, "DPR:", dpr);

      const project = (lon: number, lat: number): [number, number] =>
        projectEquirectangular(lon, lat, cssW, cssH);

      const diag: CanvasDiagnostics = {
        active: true,
        canvasWidth: cssW,
        canvasHeight: cssH,
        powerPlantsDrawn: 0,
        cableLinesDrawn: 0,
        dataCentersDrawn: 0,
        testPointsDrawn: 0,
        recordsReceived: data?.power_plants?.length || 0,
        validCoords: 0,
        lastDrawTime: new Date().toISOString(),
        lastError: null,
        projectionMode: "equirectangular",
      };

      // --- Graticule ---
      drawGraticule(ctx, cssW, cssH, project);
      console.log("[CanvasOverlay] Graticule drawn");

      // --- Power Plants ---
      if (visibleLayers.power_plants && data?.power_plants) {
        const rawPlants = data.power_plants;
        console.log("[CanvasOverlay] Total plants available:", rawPlants.length);
        const filtered: PowerPlant[] = [];
        for (const p of rawPlants) {
          const lon = getLon(p as unknown as Record<string, unknown>);
          const lat = getLat(p as unknown as Record<string, unknown>);
          if (lon == null || lat == null || !isValidLonLat(lon, lat)) continue;
          diag.validCoords++;
          if (filters.fuelType && p.f !== filters.fuelType) continue;
          if (filters.country && p.c !== filters.country) continue;
          if (filters.minMw > 0 && p.mw < filters.minMw) continue;
          filtered.push(p);
        }
        console.log("[CanvasOverlay] Valid coord count:", diag.validCoords, "After filter:", filtered.length);

        const grouped: Record<string, PowerPlant[]> = {};
        for (const p of filtered) {
          const fuel = p.f || "Other";
          if (!grouped[fuel]) grouped[fuel] = [];
          grouped[fuel].push(p);
        }

        const pointRadius = 1.8;
        for (const fuel of Object.keys(grouped)) {
          const color = FUEL_COLORS[fuel] || OTHER_COLOR;
          const plants = grouped[fuel];
          ctx.fillStyle = color;
          ctx.globalAlpha = 0.85;
          for (const p of plants) {
            const [x, y] = projectEquirectangular(p.lon, p.lat, cssW, cssH);
            if (x < -5 || x > cssW + 5 || y < -5 || y > cssH + 5) continue;
            ctx.beginPath();
            ctx.arc(x, y, pointRadius, 0, Math.PI * 2);
            ctx.fill();
            diag.powerPlantsDrawn++;
          }
        }
        ctx.globalAlpha = 1;
        console.log("[CanvasOverlay] Power plants drawn:", diag.powerPlantsDrawn);
      }

      // --- Cables ---
      if (visibleLayers.cables && data?.cables) {
        const mappedCables = data.cables.filter(
          (c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length >= 2
        );
        ctx.strokeStyle = "#4cc9e8";
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.8;
        for (const c of mappedCables) {
          if (!c.geometry || c.geometry.length < 2) continue;
          const isMultiLine = Array.isArray(c.geometry[0]) && Array.isArray(c.geometry[0][0]);
          const lines = isMultiLine ? (c.geometry as number[][][]) : [c.geometry as number[][]];
          let totalVisible = 0;
          ctx.beginPath();
          for (const line of lines) {
            if (line.length < 2) continue;
            let started = false;
            let visibleCount = 0;
            for (const coord of line) {
              const px = coord[0];
              const py = coord[1];
              if (px == null || py == null) { started = false; continue; }
              const [x, y] = projectEquirectangular(px, py, cssW, cssH);
              if (x < -200 || x > cssW + 200 || y < -200 || y > cssH + 200) {
                started = false;
                continue;
              }
              if (!started) {
                ctx.moveTo(x, y);
                started = true;
              } else {
                ctx.lineTo(x, y);
              }
              visibleCount++;
            }
            if (visibleCount >= 2) totalVisible++;
          }
          if (totalVisible > 0) {
            ctx.stroke();
            diag.cableLinesDrawn++;
          }
        }
        ctx.globalAlpha = 1;
        console.log("[CanvasOverlay] Cables drawn:", diag.cableLinesDrawn);
      }

      // --- Data Centers ---
      if (visibleLayers.data_centers && data?.data_centers) {
        const mappedDCs = data.data_centers.filter(
          (d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null
        );
        const dcRadius = 6;
        for (const d of mappedDCs) {
          const [x, y] = projectEquirectangular(d.lon!, d.lat!, cssW, cssH);
          if (x < -20 || x > cssW + 20 || y < -20 || y > cssH + 20) continue;
          ctx.beginPath();
          ctx.arc(x, y, dcRadius, 0, Math.PI * 2);
          ctx.fillStyle = "#e8e5dc";
          ctx.globalAlpha = 0.9;
          ctx.fill();
          ctx.strokeStyle = "#4cc9e8";
          ctx.lineWidth = 1.5;
          ctx.stroke();
          diag.dataCentersDrawn++;
        }
        ctx.globalAlpha = 1;
        console.log("[CanvasOverlay] Data centers drawn:", diag.dataCentersDrawn);
      }

      // --- Test Points ---
      if (showTestPoints) {
        const tpRadius = 6;
        for (const tp of TEST_POINTS) {
          const [x, y] = projectEquirectangular(tp.lon, tp.lat, cssW, cssH);
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

      if (diag.powerPlantsDrawn === 0 && diag.recordsReceived > 1000) {
        console.warn("[CanvasOverlay] ZERO POINTS DRAWN despite", diag.recordsReceived, "records and", diag.validCoords, "valid coords");
      }

      onCanvasDiagnostics?.(diag);
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      console.error("[CanvasOverlay] Draw error:", errMsg);
    }
  }, [data, filters, visibleLayers, showTestPoints, onCanvasDiagnostics]);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(() => {
      console.log("[CanvasOverlay] First draw triggered");
      draw();
    });
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [draw]);

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

    return () => resizeObsRef.current?.disconnect();
  }, [draw]);

  return <canvas ref={canvasRef} className="infrastructure-canvas" />;
}

function drawGraticule(ctx: CanvasRenderingContext2D, w: number, h: number, project: (lon: number, lat: number) => [number, number]) {
  ctx.strokeStyle = "rgba(60, 60, 70, 0.3)";
  ctx.lineWidth = 0.5;
  ctx.globalAlpha = 1;

  for (let lon = -180; lon <= 180; lon += 30) {
    const [x] = project(lon, 0);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  for (let lat = -90; lat <= 90; lat += 30) {
    const [, y] = project(0, lat);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(80, 80, 90, 0.6)";
  ctx.lineWidth = 1;
  const [, eqY] = project(0, 0);
  ctx.beginPath();
  ctx.moveTo(0, eqY);
  ctx.lineTo(w, eqY);
  ctx.stroke();

  const [pmX] = project(0, 0);
  ctx.beginPath();
  ctx.moveTo(pmX, 0);
  ctx.lineTo(pmX, h);
  ctx.stroke();
}
