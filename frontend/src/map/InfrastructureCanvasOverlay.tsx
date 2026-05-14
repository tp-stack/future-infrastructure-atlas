import { useRef, useEffect, useCallback } from "react";
import type maplibregl from "maplibre-gl";
import type { AtlasData, FilterState, PowerPlant, Cable, DataCenter } from "./types";
import { CABLE_COLOR, CABLE_HOVER_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS } from "./layers";

interface Props {
  enabled?: boolean;
  data: AtlasData;
  filters: FilterState;
  visibleLayers: Record<string, boolean>;
  mapInstance?: maplibregl.Map | null;
  showTestPoints?: boolean;
  onCanvasDiagnostics?: (d: CanvasDiagnostics) => void;
  hoveredAssetId?: string | null;
  selectedAssetId?: string | null;
  graticuleVisible?: boolean;
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
  currentZoom: number;
}

const OTHER_COLOR = "#8d93a1";

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
  enabled = true,
  data,
  filters,
  visibleLayers,
  mapInstance,
  showTestPoints,
  onCanvasDiagnostics,
  hoveredAssetId,
  selectedAssetId,
  graticuleVisible,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const animFrameRef = useRef(0);
  const resizeObsRef = useRef<ResizeObserver | null>(null);

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

      if (!enabled) {
        onCanvasDiagnostics?.({
          active: false,
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
          projectionMode: "disabled",
          currentZoom: mapInstance ? mapInstance.getZoom() : 0,
        });
        return;
      }

      const useMapProject = mapInstance && typeof mapInstance.project === "function";
      const project: (lon: number, lat: number) => [number, number] = useMapProject
        ? (lon: number, lat: number) => {
            const p = (mapInstance as maplibregl.Map).project([lon, lat]);
            return [p.x, p.y];
          }
        : (lon: number, lat: number) => projectEquirectangular(lon, lat, cssW, cssH);

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
        projectionMode: useMapProject ? "mercator (map)" : "equirectangular (fallback)",
        currentZoom: useMapProject ? (mapInstance as maplibregl.Map).getZoom() : 0,
      };

      if (graticuleVisible) {
        drawGraticule(ctx, cssW, cssH, project);
      }

      if (!useMapProject) {
        ctx.globalAlpha = 1;
        return;
      }

      if (visibleLayers.power_plants && data?.power_plants) {
        const rawPlants = data.power_plants;
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

        const grouped: Record<string, PowerPlant[]> = {};
        for (const p of filtered) {
          const fuel = p.f || "Other";
          if (!grouped[fuel]) grouped[fuel] = [];
          grouped[fuel].push(p);
        }

        const pointRadius = 2;
        const hoveredId = hoveredAssetId;
        const selectedId = selectedAssetId;

        for (const fuel of Object.keys(grouped)) {
          const color = FUEL_COLORS[fuel] || OTHER_COLOR;
          const plants = grouped[fuel];
          for (const p of plants) {
            const [x, y] = project(p.lon, p.lat);
            if (x < -5 || x > cssW + 5 || y < -5 || y > cssH + 5) continue;
            const id = `pp-${p.n}-${p.lat}-${p.lon}`;
            const isHovered = id === hoveredId;
            const isSelected = id === selectedId;

            ctx.beginPath();
            ctx.arc(x, y, pointRadius, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.globalAlpha = 0.85;
            ctx.fill();

            if (isHovered || isSelected) {
              ctx.beginPath();
              ctx.arc(x, y, isSelected ? 6 : 4, 0, Math.PI * 2);
              ctx.strokeStyle = "#ffffff";
              ctx.lineWidth = isSelected ? 2.5 : 1.5;
              ctx.globalAlpha = isSelected ? 1 : 0.8;
              ctx.stroke();
              ctx.beginPath();
              ctx.arc(x, y, pointRadius, 0, Math.PI * 2);
              ctx.fillStyle = "#ffffff";
              ctx.globalAlpha = 0.95;
              ctx.fill();
              ctx.fillStyle = color;
              ctx.globalAlpha = 0.9;
              ctx.beginPath();
              ctx.arc(x, y, pointRadius * 0.7, 0, Math.PI * 2);
              ctx.fill();
            }

            if (isSelected) {
              ctx.beginPath();
              ctx.arc(x, y, 10, 0, Math.PI * 2);
              ctx.strokeStyle = "rgba(255,255,255,0.3)";
              ctx.lineWidth = 1;
              ctx.globalAlpha = 0.5;
              ctx.stroke();
            }

            diag.powerPlantsDrawn++;
          }
        }
        ctx.globalAlpha = 1;
      }

      if (visibleLayers.cables && data?.cables) {
        const mappedCables = data.cables.filter(
          (c) => c.mapped_status === "mapped" && c.geometry && c.geometry.length > 0
        );
        for (const c of mappedCables) {
          if (!c.geometry || c.geometry.length === 0) continue;
          const isMultiLine = Array.isArray(c.geometry[0]) && Array.isArray(c.geometry[0][0]);
          const lines = isMultiLine ? (c.geometry as number[][][]) : [c.geometry as number[][]];
          const id = `cable-${c.n}`;
          const isHovered = id === hoveredAssetId;
          const isSelected = id === selectedAssetId;

          ctx.lineWidth = isSelected ? 4 : isHovered ? 3 : 2;
          ctx.strokeStyle = isSelected ? "#ffffff" : isHovered ? CABLE_HOVER_COLOR : CABLE_COLOR;
          ctx.globalAlpha = isSelected ? 1 : isHovered ? 0.95 : 0.8;

          for (const line of lines) {
            if (line.length < 2) continue;
            ctx.beginPath();
            let started = false;
            for (const coord of line) {
              const px = coord[0];
              const py = coord[1];
              if (px == null || py == null) { started = false; continue; }
              const [x, y] = project(px, py);
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
            }
            ctx.stroke();
          }
          diag.cableLinesDrawn++;
        }
        ctx.globalAlpha = 1;
      }

      if (visibleLayers.data_centers && data?.data_centers) {
        const mappedDCs = data.data_centers.filter(
          (d) => d.mapped_status === "mapped" && d.lat != null && d.lon != null
        );
        const dcRadius = 5;
        for (const d of mappedDCs) {
          const [x, y] = project(d.lon!, d.lat!);
          if (x < -20 || x > cssW + 20 || y < -20 || y > cssH + 20) continue;
          const id = `dc-${d.n}-${d.lat}-${d.lon}`;
          const isHovered = id === hoveredAssetId;
          const isSelected = id === selectedAssetId;

          ctx.beginPath();
          ctx.arc(x, y, dcRadius, 0, Math.PI * 2);
          ctx.fillStyle = DATA_CENTER_COLOR;
          ctx.globalAlpha = 0.9;
          ctx.fill();

          if (isHovered || isSelected) {
            ctx.beginPath();
            ctx.arc(x, y, dcRadius + 4, 0, Math.PI * 2);
            ctx.strokeStyle = DATA_CENTER_STROKE_COLOR;
            ctx.lineWidth = isSelected ? 3 : 2;
            ctx.globalAlpha = isSelected ? 1 : 0.8;
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(x, y, dcRadius, 0, Math.PI * 2);
            ctx.fillStyle = "#ffffff";
            ctx.globalAlpha = 0.95;
            ctx.fill();
            ctx.beginPath();
            ctx.arc(x, y, dcRadius - 2, 0, Math.PI * 2);
            ctx.fillStyle = DATA_CENTER_COLOR;
            ctx.globalAlpha = 0.9;
            ctx.fill();
          }

          ctx.strokeStyle = DATA_CENTER_STROKE_COLOR;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          diag.dataCentersDrawn++;
        }
        ctx.globalAlpha = 1;
      }

      if (showTestPoints) {
        const tpRadius = 6;
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

      if (diag.powerPlantsDrawn === 0 && diag.recordsReceived > 1000) {
        console.warn("[CanvasOverlay] ZERO POINTS DRAWN despite", diag.recordsReceived, "records and", diag.validCoords, "valid coords");
      }

      onCanvasDiagnostics?.(diag);
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e);
      console.error("[CanvasOverlay] Draw error:", errMsg);
    }
  }, [enabled, data, filters, visibleLayers, mapInstance, showTestPoints, onCanvasDiagnostics, hoveredAssetId, selectedAssetId, graticuleVisible]);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(() => { draw(); });
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
  ctx.strokeStyle = "rgba(70, 84, 96, 0.22)";
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

  ctx.strokeStyle = "rgba(70, 84, 96, 0.4)";
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
