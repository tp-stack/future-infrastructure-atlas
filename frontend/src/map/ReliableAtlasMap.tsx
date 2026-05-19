import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AtlasData, Asset, FilterState } from "./types";
import type { InteractableType } from "./interaction";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS } from "./layers";
import {
  buildCableGeoJSON,
  buildDataCenterGeoJSON,
  buildGraticuleGeoJSON,
  buildPowerPlantGeoJSON,
  computeCombinedBounds,
  type LonLatBounds,
} from "./geojson";

interface Props {
  data: AtlasData;
  filters?: FilterState;
  visibleLayers?: Record<string, boolean>;
  graticuleVisible?: boolean;
  proof?: boolean;
  onAssetSelect?: (asset: Asset | null, assetType: InteractableType | null) => void;
}

interface ViewState {
  centerLon: number;
  centerLat: number;
  zoom: number;
}

interface DrawItem {
  kind: "cluster" | "power_plant" | "data_center" | "submarine_cable" | "proof";
  x: number;
  y: number;
  r: number;
  lon: number;
  lat: number;
  count?: number;
  title: string;
  rows: Array<[string, unknown]>;
  asset?: Asset;
  assetType?: InteractableType;
  line?: Array<[number, number]>;
}

interface PopupState {
  x: number;
  y: number;
  title: string;
  rows: Array<[string, unknown]>;
}

const EMPTY_FILTERS: FilterState = { fuelType: "", country: "", minMw: 0 };
const DEFAULT_VISIBLE_LAYERS = { power_plants: true, cables: true, data_centers: true };
const INITIAL_VIEW: ViewState = { centerLon: 10, centerLat: 20, zoom: 1 };
const WORLD_BOUNDS: LonLatBounds = { minLon: -179.5, minLat: -65, maxLon: 179.5, maxLat: 82 };
const PROOF_POINTS = [
  { n: "London", lon: -0.1278, lat: 51.5074 },
  { n: "New York", lon: -74.006, lat: 40.7128 },
  { n: "Singapore", lon: 103.8198, lat: 1.3521 },
  { n: "Tokyo", lon: 139.6503, lat: 35.6762 },
  { n: "Sao Paulo", lon: -46.6333, lat: -23.5505 },
];

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function baseScale(width: number, height: number): number {
  return Math.max(1, Math.min(width / 360, height / 170) * 0.94);
}

function project(lon: number, lat: number, width: number, height: number, view: ViewState): [number, number] {
  const scale = baseScale(width, height) * view.zoom;
  return [
    width / 2 + (lon - view.centerLon) * scale,
    height / 2 - (lat - view.centerLat) * scale,
  ];
}

function unproject(x: number, y: number, width: number, height: number, view: ViewState): [number, number] {
  const scale = baseScale(width, height) * view.zoom;
  return [
    view.centerLon + (x - width / 2) / scale,
    view.centerLat - (y - height / 2) / scale,
  ];
}

function clampView(view: ViewState): ViewState {
  return {
    centerLon: clamp(view.centerLon, -180, 180),
    centerLat: clamp(view.centerLat, -75, 75),
    zoom: clamp(view.zoom, 0.75, 28),
  };
}

function geometryLines(geometry: GeoJSON.Geometry | null): number[][][] {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates as number[][]];
  if (geometry.type === "MultiLineString") return geometry.coordinates as number[][][];
  return [];
}

function distanceToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return Math.hypot(px - ax, py - ay);
  const t = clamp(((px - ax) * dx + (py - ay) * dy) / len2, 0, 1);
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function lineHitDistance(item: DrawItem, x: number, y: number): number {
  if (!item.line || item.line.length < 2) return Infinity;
  let min = Infinity;
  for (let i = 1; i < item.line.length; i += 1) {
    const [ax, ay] = item.line[i - 1];
    const [bx, by] = item.line[i];
    min = Math.min(min, distanceToSegment(x, y, ax, ay, bx, by));
  }
  return min;
}

function rowsHtml(rows: Array<[string, unknown]>): JSX.Element[] {
  return rows
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([label, value]) => (
      <div className="reliable-popup-row" key={`${label}-${String(value)}`}>
        <span>{label}</span>
        <strong>{String(value)}</strong>
      </div>
    ));
}

function pointAsset(kind: "power_plant" | "data_center", props: GeoJSON.GeoJsonProperties, lon: number, lat: number): {
  asset: Asset;
  assetType: InteractableType;
} {
  if (kind === "power_plant") {
    return {
      assetType: "power_plant",
      asset: {
        n: String(props?.n || props?.name || ""),
        c: String(props?.c || props?.country || ""),
        f: String(props?.f || props?.fuel || ""),
        mw: Number(props?.mw ?? props?.capacity_mw ?? 0),
        lon,
        lat,
        mapped_status: "mapped",
      },
    };
  }

  return {
    assetType: "data_center",
    asset: {
      n: String(props?.n || props?.name || ""),
      op: String(props?.op || props?.operator || ""),
      c: String(props?.c || props?.country || ""),
      city: String(props?.city || ""),
      lon,
      lat,
      source: String(props?.source || ""),
      coordinate_precision: String(props?.coordinate_precision || ""),
      source_license: String(props?.source_license || ""),
      confidence: Number(props?.confidence ?? 0),
      mapped_status: "mapped",
      net_count: Number(props?.net_count ?? 0),
      ix_count: Number(props?.ix_count ?? 0),
    },
  };
}

function cableAsset(props: GeoJSON.GeoJsonProperties): Asset {
  return {
    n: String(props?.n || props?.name || ""),
    source: String(props?.source || ""),
    geometry: [],
    mapped_status: "mapped",
    source_license: String(props?.source_license || ""),
    geometry_precision: String(props?.geometry_precision || ""),
    confidence: Number(props?.confidence ?? 0),
    operators: String(props?.operators || ""),
    landing_points: String(props?.landing_points || ""),
    length_km: String(props?.length_km || ""),
  };
}

export default function ReliableAtlasMap({
  data,
  filters = EMPTY_FILTERS,
  visibleLayers = DEFAULT_VISIBLE_LAYERS,
  graticuleVisible = true,
  proof = false,
  onAssetSelect,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const drawItemsRef = useRef<DrawItem[]>([]);
  const dragRef = useRef<{ id: number; x: number; y: number; moved: boolean } | null>(null);
  const lastPointerActivationRef = useRef(0);
  const [size, setSize] = useState({ width: 1, height: 1, dpr: 1 });
  const [view, setView] = useState<ViewState>(INITIAL_VIEW);
  const [popup, setPopup] = useState<PopupState | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const collections = useMemo(() => ({
    power: buildPowerPlantGeoJSON(data, filters),
    dataCenters: buildDataCenterGeoJSON(data, filters),
    cables: buildCableGeoJSON(data),
    graticule: buildGraticuleGeoJSON(),
  }), [data, filters]);

  const resetGlobalView = useCallback(() => {
    setView(INITIAL_VIEW);
    setPopup(null);
  }, []);

  const fitToData = useCallback(() => {
    const bounds = computeCombinedBounds([collections.power, collections.dataCenters, collections.cables]) || WORLD_BOUNDS;
    const lonSpan = Math.max(8, bounds.maxLon - bounds.minLon);
    const latSpan = Math.max(8, bounds.maxLat - bounds.minLat);
    const usableWidth = Math.max(120, size.width - 120);
    const usableHeight = Math.max(120, size.height - 120);
    const scale = baseScale(size.width, size.height);
    const nextZoom = clamp(Math.min(usableWidth / (lonSpan * scale), usableHeight / (latSpan * scale)), 0.85, 8);
    setView(clampView({
      centerLon: (bounds.minLon + bounds.maxLon) / 2,
      centerLat: (bounds.minLat + bounds.maxLat) / 2,
      zoom: nextZoom,
    }));
    setPopup(null);
  }, [collections, size]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;

    const resize = () => {
      const rect = node.getBoundingClientRect();
      setSize({
        width: Math.max(1, rect.width),
        height: Math.max(1, rect.height),
        dpr: Math.max(1, window.devicePixelRatio || 1),
      });
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const { width, height, dpr } = size;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const items: DrawItem[] = [];
    ctx.fillStyle = "#05070a";
    ctx.fillRect(0, 0, width, height);

    const worldTopLeft = project(-180, 85, width, height, view);
    const worldBottomRight = project(180, -85, width, height, view);
    ctx.fillStyle = "#07111d";
    ctx.fillRect(worldTopLeft[0], worldTopLeft[1], worldBottomRight[0] - worldTopLeft[0], worldBottomRight[1] - worldTopLeft[1]);
    ctx.strokeStyle = "rgba(255,255,255,0.16)";
    ctx.lineWidth = 1;
    ctx.strokeRect(worldTopLeft[0], worldTopLeft[1], worldBottomRight[0] - worldTopLeft[0], worldBottomRight[1] - worldTopLeft[1]);

    if (graticuleVisible) {
      ctx.strokeStyle = "rgba(148, 163, 184, 0.22)";
      ctx.lineWidth = 1;
      for (const feature of collections.graticule.features) {
        const lines = geometryLines(feature.geometry);
        for (const line of lines) {
          ctx.beginPath();
          line.forEach(([lon, lat], i) => {
            const [x, y] = project(lon, lat, width, height, view);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.stroke();
        }
      }
    }

    if (visibleLayers.cables) {
      ctx.strokeStyle = CABLE_COLOR;
      ctx.lineWidth = Math.max(1.4, Math.min(4, view.zoom * 1.1));
      ctx.globalAlpha = 0.9;
      for (const feature of collections.cables.features) {
        const props = feature.properties || {};
        const lines = geometryLines(feature.geometry);
        for (const line of lines) {
          const screenLine: Array<[number, number]> = [];
          ctx.beginPath();
          line.forEach(([lon, lat], i) => {
            const [x, y] = project(lon, lat, width, height, view);
            screenLine.push([x, y]);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.stroke();
          if (screenLine.length > 1) {
            const mid = screenLine[Math.floor(screenLine.length / 2)];
            const geoMid = line[Math.floor(line.length / 2)];
            items.push({
              kind: "submarine_cable",
              x: mid[0],
              y: mid[1],
              r: 8,
              lon: geoMid[0],
              lat: geoMid[1],
              title: String(props.n || props.name || "Submarine cable"),
              rows: [["Source", props.source], ["License", props.source_license], ["Precision", props.geometry_precision], ["Confidence", props.confidence]],
              asset: cableAsset(props),
              assetType: "submarine_cable",
              line: screenLine,
            });
          }
        }
      }
      ctx.globalAlpha = 1;
    }

    if (visibleLayers.power_plants) {
      const cellSize = view.zoom < 5 ? (view.zoom < 2 ? 36 : 26) : 0;
      const clusters = new Map<string, { x: number; y: number; lon: number; lat: number; count: number; props?: GeoJSON.GeoJsonProperties }>();
      for (const feature of collections.power.features) {
        if (feature.geometry.type !== "Point") continue;
        const [lon, lat] = feature.geometry.coordinates;
        const [x, y] = project(lon, lat, width, height, view);
        if (x < -50 || y < -50 || x > width + 50 || y > height + 50) continue;

        if (cellSize > 0) {
          const key = `${Math.floor(x / cellSize)}:${Math.floor(y / cellSize)}`;
          const cluster = clusters.get(key);
          if (cluster) {
            cluster.x += x;
            cluster.y += y;
            cluster.lon += lon;
            cluster.lat += lat;
            cluster.count += 1;
          } else {
            clusters.set(key, { x, y, lon, lat, count: 1, props: feature.properties });
          }
        } else {
          clusters.set(`${x}:${y}`, { x, y, lon, lat, count: 1, props: feature.properties });
        }
      }

      for (const cluster of clusters.values()) {
        const x = cluster.x / cluster.count;
        const y = cluster.y / cluster.count;
        const lon = cluster.lon / cluster.count;
        const lat = cluster.lat / cluster.count;
        if (cluster.count > 1) {
          const r = clamp(8 + Math.log(cluster.count) * 4, 12, 31);
          ctx.beginPath();
          ctx.fillStyle = cluster.count > 250 ? "#d97706" : cluster.count > 25 ? "#f59e0b" : "#f7c948";
          ctx.strokeStyle = "#fff7cc";
          ctx.lineWidth = 1.5;
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = "#111827";
          ctx.font = "700 11px Inter, system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(cluster.count >= 1000 ? `${Math.round(cluster.count / 100) / 10}k` : String(cluster.count), x, y);
          items.push({ kind: "cluster", x, y, r, lon, lat, count: cluster.count, title: `${cluster.count.toLocaleString()} power plants`, rows: [["Action", "Click to zoom in"]] });
        } else {
          const props = cluster.props || {};
          const color = String(props.f || "") in FUEL_COLORS ? FUEL_COLORS[String(props.f || "") as keyof typeof FUEL_COLORS] : FUEL_COLORS.Other;
          ctx.beginPath();
          ctx.fillStyle = color;
          ctx.strokeStyle = "rgba(255,255,255,0.78)";
          ctx.lineWidth = 0.9;
          ctx.arc(x, y, clamp(2.4 + view.zoom * 0.6, 3, 7), 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
          const { asset, assetType } = pointAsset("power_plant", props, lon, lat);
          items.push({
            kind: "power_plant",
            x,
            y,
            r: 8,
            lon,
            lat,
            title: String(props.n || props.name || "Power plant"),
            rows: [["Fuel", props.f || props.fuel], ["Capacity", props.mw ? `${props.mw} MW` : props.capacity_mw], ["Country", props.c || props.country]],
            asset,
            assetType,
          });
        }
      }
    }

    if (visibleLayers.data_centers) {
      for (const feature of collections.dataCenters.features) {
        if (feature.geometry.type !== "Point") continue;
        const [lon, lat] = feature.geometry.coordinates;
        const [x, y] = project(lon, lat, width, height, view);
        if (x < -30 || y < -30 || x > width + 30 || y > height + 30) continue;
        const props = feature.properties || {};
        ctx.beginPath();
        ctx.fillStyle = DATA_CENTER_COLOR;
        ctx.strokeStyle = DATA_CENTER_STROKE_COLOR;
        ctx.lineWidth = 2;
        ctx.arc(x, y, clamp(4 + view.zoom * 0.45, 4.5, 9), 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        const { asset, assetType } = pointAsset("data_center", props, lon, lat);
        items.push({
          kind: "data_center",
          x,
          y,
          r: 10,
          lon,
          lat,
          title: String(props.n || props.name || "Data center"),
          rows: [["Operator", props.op || props.operator], ["Country", props.c || props.country], ["City", props.city], ["Precision", props.coordinate_precision], ["Source", props.source]],
          asset,
          assetType,
        });
      }
    }

    if (proof) {
      for (const p of PROOF_POINTS) {
        const [x, y] = project(p.lon, p.lat, width, height, view);
        ctx.beginPath();
        ctx.fillStyle = "#ef4444";
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;
        ctx.arc(x, y, 13, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        items.push({ kind: "proof", x, y, r: 16, lon: p.lon, lat: p.lat, title: p.n, rows: [["Proof route", "visible"]] });
      }
    }

    drawItemsRef.current = items;
  }, [collections, graticuleVisible, proof, size, view, visibleLayers]);

  const hitTest = useCallback((x: number, y: number): DrawItem | null => {
    const items = drawItemsRef.current;
    let best: { item: DrawItem; distance: number } | null = null;
    for (let i = items.length - 1; i >= 0; i -= 1) {
      const item = items[i];
      const distance = item.line ? lineHitDistance(item, x, y) : Math.hypot(x - item.x, y - item.y);
      const threshold = item.line ? 8 : item.r + 3;
      if (distance <= threshold && (!best || distance < best.distance)) best = { item, distance };
    }
    return best?.item || null;
  }, []);

  const eventPoint = useCallback((event: React.PointerEvent | React.MouseEvent | React.WheelEvent): [number, number] => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return [0, 0];
    return [event.clientX - rect.left, event.clientY - rect.top];
  }, []);

  const handleWheel = useCallback((event: React.WheelEvent) => {
    event.preventDefault();
    const [x, y] = eventPoint(event);
    const before = unproject(x, y, size.width, size.height, view);
    const factor = Math.exp(-event.deltaY * 0.0012);
    const nextZoom = clamp(view.zoom * factor, 0.75, 28);
    const scale = baseScale(size.width, size.height) * nextZoom;
    const nextCenterLon = before[0] - (x - size.width / 2) / scale;
    const nextCenterLat = before[1] + (y - size.height / 2) / scale;
    setView(clampView({ centerLon: nextCenterLon, centerLat: nextCenterLat, zoom: nextZoom }));
    setPopup(null);
  }, [eventPoint, size, view]);

  const handlePointerDown = useCallback((event: React.PointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
  }, []);

  const handlePointerMove = useCallback((event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (drag && drag.id === event.pointerId) {
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
      drag.x = event.clientX;
      drag.y = event.clientY;
      const scale = baseScale(size.width, size.height) * view.zoom;
      setView((current) => clampView({
        ...current,
        centerLon: current.centerLon - dx / scale,
        centerLat: current.centerLat + dy / scale,
      }));
      setPopup(null);
      return;
    }

    const [x, y] = eventPoint(event);
    const hit = hitTest(x, y);
    setHovered(hit ? hit.title : null);
  }, [eventPoint, hitTest, size, view.zoom]);

  const activateAt = useCallback((x: number, y: number) => {
    const hit = hitTest(x, y);
    if (!hit) {
      setPopup(null);
      onAssetSelect?.(null, null);
      return;
    }

    if (hit.kind === "cluster") {
      setView((current) => clampView({ centerLon: hit.lon, centerLat: hit.lat, zoom: Math.min(28, current.zoom * 2.2) }));
      setPopup(null);
      return;
    }

    setPopup({ x: hit.x, y: hit.y, title: hit.title, rows: hit.rows });
    if (hit.asset && hit.assetType) onAssetSelect?.(hit.asset, hit.assetType);
  }, [hitTest, onAssetSelect]);

  const handlePointerUp = useCallback((event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (drag?.moved) return;

    const [x, y] = eventPoint(event);
    lastPointerActivationRef.current = Date.now();
    activateAt(x, y);
  }, [activateAt, eventPoint]);

  const handleClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (Date.now() - lastPointerActivationRef.current < 250) return;
    const [x, y] = eventPoint(event);
    activateAt(x, y);
  }, [activateAt, eventPoint]);

  const handleDoubleClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const [x, y] = eventPoint(event);
    const [lon, lat] = unproject(x, y, size.width, size.height, view);
    setView(clampView({ centerLon: lon, centerLat: lat, zoom: view.zoom * 1.8 }));
    setPopup(null);
  }, [eventPoint, size, view]);

  return (
    <div ref={containerRef} className="reliable-atlas">
      <canvas
        ref={canvasRef}
        className="reliable-atlas-canvas"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
      />

      <div className="reliable-debug">
        <div className="reliable-debug-title">{proof ? "PROOF CANVAS MAP" : "RELIABLE CANVAS MAP"}</div>
        <div>Power: {collections.power.features.length.toLocaleString()}</div>
        <div>Data centers: {collections.dataCenters.features.length.toLocaleString()}</div>
        <div>Cables: {collections.cables.features.length.toLocaleString()}</div>
        <div>Zoom: {view.zoom.toFixed(2)}</div>
        <div>Center: {view.centerLat.toFixed(2)}, {view.centerLon.toFixed(2)}</div>
        {hovered && <div className="reliable-hover">Hover: {hovered}</div>}
      </div>

      <div className="reliable-controls">
        <button type="button" onClick={resetGlobalView}>Reset Global View</button>
        <button type="button" onClick={fitToData}>Fit Filtered Results</button>
      </div>

      {popup && (
        <div className="reliable-popup" style={{ left: popup.x, top: popup.y }}>
          <button type="button" onClick={() => setPopup(null)} aria-label="Close popup">x</button>
          <div className="reliable-popup-title">{popup.title}</div>
          {rowsHtml(popup.rows)}
        </div>
      )}
    </div>
  );
}
