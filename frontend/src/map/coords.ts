export function parseCoord(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function getLon(record: Record<string, unknown>): number | null {
  return parseCoord(record.lon ?? record.longitude ?? record.lng ?? null);
}

export function getLat(record: Record<string, unknown>): number | null {
  return parseCoord(record.lat ?? record.latitude ?? null);
}

export function isValidLonLat(lon: number, lat: number): boolean {
  return isFinite(lon) && isFinite(lat) && lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90;
}

export function validPointFromRecord(record: Record<string, unknown>): [number, number] | null {
  const lon = getLon(record);
  const lat = getLat(record);
  if (lon == null || lat == null || !isValidLonLat(lon, lat)) return null;
  return [lon, lat];
}

export function toValidPoint(coord: unknown): [number, number] | null {
  if (!Array.isArray(coord) || coord.length < 2) return null;
  const lon = parseCoord(coord[0]);
  const lat = parseCoord(coord[1]);
  if (lon == null || lat == null || !isValidLonLat(lon, lat)) return null;
  return [lon, lat];
}
