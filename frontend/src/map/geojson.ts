import type { AtlasData, FilterState, PowerPlant, DataCenter, Cable } from "./types";

function isValidCoord(v: unknown): v is number {
  return typeof v === "number" && isFinite(v);
}

function parseCoord(v: unknown): number | null {
  if (typeof v === "number" && isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v);
    return isFinite(n) ? n : null;
  }
  return null;
}

export function buildPowerPlantGeoJSON(
  data: AtlasData,
  filters: FilterState,
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (const p of data.power_plants) {
    if (filters.fuelType && p.f !== filters.fuelType) continue;
    if (filters.country && p.c !== filters.country) continue;
    if (filters.minMw > 0 && p.mw < filters.minMw) continue;

    const lon = parseCoord(p.lon);
    const lat = parseCoord(p.lat);
    if (lon == null || lat == null) continue;
    if (lon < -180 || lon > 180 || lat < -90 || lat > 90) continue;

    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        name: p.n || "",
        country: p.c || "",
        fuel: p.f || "",
        capacity_mw: p.mw ?? 0,
        lat,
        lon,
      },
    });
  }

  return { type: "FeatureCollection", features };
}

export function buildDataCenterGeoJSON(
  data: AtlasData,
  filters: FilterState,
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (const d of data.data_centers) {
    if (d.mapped_status !== "mapped") continue;

    const lon = parseCoord(d.lon);
    const lat = parseCoord(d.lat);
    if (lon == null || lat == null) continue;
    if (lon < -180 || lon > 180 || lat < -90 || lat > 90) continue;

    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        name: d.n || "",
        operator: d.op || "",
        country: d.c || "",
        city: d.city || "",
        coordinate_precision: d.coordinate_precision || "",
        source_license: d.source_license || "",
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
  const seen = new Set<string>();

  for (const c of data.cables) {
    if (c.mapped_status !== "mapped" || !c.geometry || c.geometry.length < 2) continue;

    const isMulti = Array.isArray(c.geometry[0]) && Array.isArray(c.geometry[0][0]);
    const coords = isMulti ? (c.geometry as number[][][]) : [c.geometry as number[][]];

    // Deduplicate by cable name
    if (seen.has(c.n)) continue;
    seen.add(c.n);

    const validLines: number[][][] = [];
    for (const line of coords) {
      const valid: number[][] = [];
      for (const coord of line) {
        const [lon, lat] = coord;
        if (lon == null || lat == null) continue;
        if (!isFinite(lon) || !isFinite(lat)) continue;
        if (lon < -180 || lon > 180 || lat < -90 || lat > 90) continue;
        valid.push([lon, lat]);
      }
      if (valid.length >= 2) validLines.push(valid);
    }

    if (validLines.length === 0) continue;

    const geometry: GeoJSON.Geometry = validLines.length === 1
      ? { type: "LineString", coordinates: validLines[0] }
      : { type: "MultiLineString", coordinates: validLines };

    features.push({
      type: "Feature",
      geometry,
      properties: {
        name: c.n || "",
        source: c.source || "",
        geometry_precision: c.geometry_precision || "",
        source_license: c.source_license || "",
        confidence: c.confidence ?? 0,
      },
    });
  }

  return { type: "FeatureCollection", features };
}
