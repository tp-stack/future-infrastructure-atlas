import type { AtlasData, FilterState } from "./types";

export interface LonLatBounds {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export function getValidAssetCoordinates(
  data: AtlasData,
  filters: FilterState,
  layers: Record<string, boolean>,
): [number, number][] {
  const coords: [number, number][] = [];

  if (layers.power_plants) {
    for (const p of data.power_plants) {
      if (filters.fuelType && p.f !== filters.fuelType) continue;
      if (filters.country && p.c !== filters.country) continue;
      if (filters.minMw > 0 && p.mw < filters.minMw) continue;
      const lon = (p as unknown as Record<string, number | undefined>).lon ?? (p as unknown as Record<string, number | undefined>).longitude;
      const lat = (p as unknown as Record<string, number | undefined>).lat ?? (p as unknown as Record<string, number | undefined>).latitude;
      if (lon == null || lat == null) continue;
      if (!isFinite(lon) || !isFinite(lat)) continue;
      if (lon < -180 || lon > 180 || lat < -90 || lat > 90) continue;
      coords.push([lon, lat]);
    }
  }

  if (layers.data_centers) {
    for (const d of data.data_centers) {
      if (d.mapped_status !== "mapped") continue;
      const lon = d.lon ?? (d as unknown as Record<string, number | undefined>).longitude;
      const lat = d.lat ?? (d as unknown as Record<string, number | undefined>).latitude;
      if (lon == null || lat == null) continue;
      if (!isFinite(lon) || !isFinite(lat)) continue;
      if (lon < -180 || lon > 180 || lat < -90 || lat > 90) continue;
      coords.push([lon, lat]);
    }
  }

  if (layers.cables) {
    for (const c of data.cables) {
      if (c.mapped_status !== "mapped" || !c.geometry) continue;
      const isMulti = Array.isArray(c.geometry[0]) && Array.isArray(c.geometry[0][0]);
      const lines = isMulti ? (c.geometry as number[][][]) : [c.geometry as number[][]];
      for (const line of lines) {
        for (const coord of line) {
          const [lon, lat] = coord;
          if (lon == null || lat == null) continue;
          if (!isFinite(lon) || !isFinite(lat)) continue;
          if (lon < -180 || lon > 180 || lat < -90 || lat > 90) continue;
          coords.push([lon, lat]);
        }
      }
    }
  }

  return coords;
}

export function computeLonLatBounds(coords: [number, number][]): LonLatBounds | null {
  if (coords.length === 0) return null;
  let minLon = Infinity, maxLon = -Infinity;
  let minLat = Infinity, maxLat = -Infinity;
  for (const [lon, lat] of coords) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  return { minLon, minLat, maxLon, maxLat };
}

export function expandBounds(bounds: LonLatBounds, padDeg: number): LonLatBounds {
  return {
    minLon: Math.max(-180, bounds.minLon - padDeg),
    minLat: Math.max(-85, bounds.minLat - padDeg),
    maxLon: Math.min(180, bounds.maxLon + padDeg),
    maxLat: Math.min(85, bounds.maxLat + padDeg),
  };
}

export function getDefaultGlobalBounds(): LonLatBounds {
  return { minLon: -180, minLat: -60, maxLon: 180, maxLat: 85 };
}

export function boundsToFitBounds(b: LonLatBounds): [[number, number], [number, number]] {
  return [[b.minLon, b.minLat], [b.maxLon, b.maxLat]];
}

export function computeFeatureCollectionBounds(fc: GeoJSON.FeatureCollection): LonLatBounds | null {
  const coords: [number, number][] = [];
  for (const f of fc.features) {
    if (f.geometry.type === "Point") {
      const c = (f.geometry as GeoJSON.Point).coordinates;
      coords.push([c[0], c[1]]);
    } else if (f.geometry.type === "LineString") {
      for (const c of (f.geometry as GeoJSON.LineString).coordinates) {
        coords.push([c[0], c[1]]);
      }
    } else if (f.geometry.type === "MultiLineString") {
      for (const line of (f.geometry as GeoJSON.MultiLineString).coordinates) {
        for (const c of line) coords.push([c[0], c[1]]);
      }
    }
  }
  return computeLonLatBounds(coords);
}

export function isZoomPathological(zoom: number): boolean {
  return zoom > 8;
}

export function describeZoomLevel(zoom: number): string {
  if (zoom > 12) return "street (pathological)";
  if (zoom > 8) return "zoomed in (pathological)";
  if (zoom > 5) return "regional";
  if (zoom > 2) return "continental";
  return "global";
}
