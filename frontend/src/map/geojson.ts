import type { AtlasData, FilterState } from "./types";

export interface LonLatBounds {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

const EMPTY_FILTERS: FilterState = { fuelType: "", country: "", minMw: 0 };

function parseCoord(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function getLon(record: Record<string, unknown>): number | null {
  return parseCoord(record.lon ?? record.longitude ?? record.lng);
}

function getLat(record: Record<string, unknown>): number | null {
  return parseCoord(record.lat ?? record.latitude);
}

function isValidLonLat(lon: number, lat: number): boolean {
  return lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90;
}

function validPointFromRecord(record: Record<string, unknown>): [number, number] | null {
  const lon = getLon(record);
  const lat = getLat(record);
  if (lon == null || lat == null || !isValidLonLat(lon, lat)) return null;
  return [lon, lat];
}

function toValidPoint(coord: unknown): [number, number] | null {
  if (!Array.isArray(coord) || coord.length < 2) return null;
  const lon = parseCoord(coord[0]);
  const lat = parseCoord(coord[1]);
  if (lon == null || lat == null || !isValidLonLat(lon, lat)) return null;
  return [lon, lat];
}

function cableLines(geometry: unknown): [number, number][][] {
  if (!Array.isArray(geometry) || geometry.length === 0) return [];

  const looksMultiLine =
    Array.isArray(geometry[0]) &&
    Array.isArray((geometry[0] as unknown[])[0]);

  const rawLines = looksMultiLine ? (geometry as unknown[]) : [geometry];
  const lines: [number, number][][] = [];

  for (const rawLine of rawLines) {
    if (!Array.isArray(rawLine)) continue;
    const line: [number, number][] = [];
    for (const rawPoint of rawLine) {
      const point = toValidPoint(rawPoint);
      if (point) line.push(point);
    }
    if (line.length >= 2) lines.push(line);
  }

  return lines;
}

export function buildPowerPlantGeoJSON(
  data: AtlasData,
  filters: FilterState = EMPTY_FILTERS,
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  let idx = 0;

  for (const p of data.power_plants) {
    if (filters.fuelType && p.f !== filters.fuelType) continue;
    if (filters.country && p.c !== filters.country) continue;
    if (filters.minMw > 0 && p.mw < filters.minMw) continue;

    const point = validPointFromRecord(p as unknown as Record<string, unknown>);
    if (!point) continue;
    const [lon, lat] = point;
    const name = p.n || "";
    const country = p.c || "";
    const fuel = p.f || "";
    const mw = p.mw ?? 0;

    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        n: name,
        c: country,
        f: fuel,
        mw,
        source: (p as unknown as Record<string, unknown>).source || "",
        name,
        country,
        fuel,
        capacity_mw: mw,
        lat,
        lon,
        _idx: idx++,
      },
    });
  }

  return { type: "FeatureCollection", features };
}

export function buildDataCenterGeoJSON(
  data: AtlasData,
  _filters: FilterState = EMPTY_FILTERS,
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (const d of data.data_centers) {
    if (d.mapped_status !== "mapped") continue;

    const point = validPointFromRecord(d as unknown as Record<string, unknown>);
    if (!point) continue;
    const [lon, lat] = point;
    const name = d.n || "";
    const operator = d.op || "";
    const country = d.c || "";

    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        n: name,
        op: operator,
        c: country,
        city: d.city || "",
        coordinate_precision: d.coordinate_precision || "",
        source_license: d.source_license || "",
        confidence: d.confidence ?? 0,
        source: d.source || "",
        name,
        operator,
        country,
        net_count: d.net_count ?? 0,
        ix_count: d.ix_count ?? 0,
        lat,
        lon,
      },
    });
  }

  return { type: "FeatureCollection", features };
}

export function buildCableGeoJSON(data: AtlasData): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (const c of data.cables) {
    if (c.mapped_status !== "mapped") continue;

    const lines = cableLines(c.geometry);
    if (lines.length === 0) continue;

    const geometry: GeoJSON.Geometry = lines.length === 1
      ? { type: "LineString", coordinates: lines[0] }
      : { type: "MultiLineString", coordinates: lines };
    const name = c.n || "";

    features.push({
      type: "Feature",
      geometry,
      properties: {
        n: name,
        source: c.source || "",
        source_license: c.source_license || "",
        geometry_precision: c.geometry_precision || "",
        confidence: c.confidence ?? 0,
        name,
        operators: c.operators || "",
        landing_points: c.landing_points || "",
        length_km: c.length_km || "",
      },
    });
  }

  return { type: "FeatureCollection", features };
}

export function buildGraticuleGeoJSON(): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (let lon = -180; lon <= 180; lon += 30) {
    const coords: [number, number][] = [];
    for (let lat = -85; lat <= 85; lat += 5) coords.push([lon, lat]);
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
      properties: { kind: "meridian", value: lon },
    });
  }

  for (let lat = -60; lat <= 75; lat += 15) {
    const coords: [number, number][] = [];
    for (let lon = -180; lon <= 180; lon += 5) coords.push([lon, lat]);
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
      properties: { kind: "parallel", value: lat },
    });
  }

  return { type: "FeatureCollection", features };
}

function addCoord(bounds: LonLatBounds | null, coord: GeoJSON.Position): LonLatBounds {
  const lon = parseCoord(coord[0]);
  const lat = parseCoord(coord[1]);
  if (lon == null || lat == null || !isValidLonLat(lon, lat)) {
    return bounds || { minLon: Infinity, minLat: Infinity, maxLon: -Infinity, maxLat: -Infinity };
  }
  if (!bounds) return { minLon: lon, minLat: lat, maxLon: lon, maxLat: lat };
  return {
    minLon: Math.min(bounds.minLon, lon),
    minLat: Math.min(bounds.minLat, lat),
    maxLon: Math.max(bounds.maxLon, lon),
    maxLat: Math.max(bounds.maxLat, lat),
  };
}

function collectGeometryBounds(bounds: LonLatBounds | null, geometry: GeoJSON.Geometry | null): LonLatBounds | null {
  if (!geometry) return bounds;

  if (geometry.type === "Point") return addCoord(bounds, geometry.coordinates);
  if (geometry.type === "MultiPoint" || geometry.type === "LineString") {
    return geometry.coordinates.reduce((b, coord) => addCoord(b, coord), bounds);
  }
  if (geometry.type === "MultiLineString" || geometry.type === "Polygon") {
    return geometry.coordinates.reduce((b, line) => line.reduce((lb, coord) => addCoord(lb, coord), b), bounds);
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.reduce(
      (b, polygon) => polygon.reduce((pb, line) => line.reduce((lb, coord) => addCoord(lb, coord), pb), b),
      bounds,
    );
  }
  if (geometry.type === "GeometryCollection") {
    return geometry.geometries.reduce((b, child) => collectGeometryBounds(b, child), bounds);
  }

  return bounds;
}

export function computeFeatureCollectionBounds(fc: GeoJSON.FeatureCollection): LonLatBounds | null {
  const bounds = fc.features.reduce<LonLatBounds | null>(
    (current, feature) => collectGeometryBounds(current, feature.geometry),
    null,
  );

  if (!bounds || !Number.isFinite(bounds.minLon) || !Number.isFinite(bounds.minLat)) return null;
  return bounds;
}

export function computeCombinedBounds(
  collections: Array<GeoJSON.FeatureCollection | null | undefined>,
): LonLatBounds | null {
  let combined: LonLatBounds | null = null;

  for (const collection of collections) {
    if (!collection) continue;
    const bounds = computeFeatureCollectionBounds(collection);
    if (!bounds) continue;
    combined = combined
      ? {
          minLon: Math.min(combined.minLon, bounds.minLon),
          minLat: Math.min(combined.minLat, bounds.minLat),
          maxLon: Math.max(combined.maxLon, bounds.maxLon),
          maxLat: Math.max(combined.maxLat, bounds.maxLat),
        }
      : bounds;
  }

  return combined;
}
