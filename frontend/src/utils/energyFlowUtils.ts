import type { PowerPlant, AtlasData } from "../map/types";

export interface EnergyFactoryDestination {
  name: string;
  type: "data_center" | "substation";
  lat: number;
  lon: number;
  distanceKm: number;
}

export function capacityToRadius(mw: number): number {
  if (mw <= 0) return 3;
  if (mw < 10) return 3 + (mw / 10) * 2;
  if (mw < 100) return 5 + ((mw - 10) / 90) * 3;
  if (mw < 1000) return 8 + ((mw - 100) / 900) * 4;
  return Math.min(14, 12 + Math.log10(mw / 1000) * 2);
}

export function haversineKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function calculateNearbyDestinations(
  plant: PowerPlant,
  data: AtlasData,
  maxDistanceKm: number = 200,
): EnergyFactoryDestination[] {
  const destinations: EnergyFactoryDestination[] = [];

  for (const dc of data.data_centers) {
    if (dc.mapped_status !== "mapped") continue;
    const dist = haversineKm(plant.lon, plant.lat, dc.lon, dc.lat);
    if (dist <= maxDistanceKm) {
      destinations.push({ name: dc.n, type: "data_center", lat: dc.lat, lon: dc.lon, distanceKm: Math.round(dist) });
    }
  }

  destinations.sort((a, b) => a.distanceKm - b.distanceKm);
  return destinations.slice(0, 10);
}

export function buildFlowLine(
  plant: PowerPlant,
  dest: EnergyFactoryDestination,
): GeoJSON.Feature {
  const lon1 = plant.lon;
  const lat1 = plant.lat;
  const lon2 = dest.lon;
  const lat2 = dest.lat;
  const midLon = (lon1 + lon2) / 2;
  const midLat = (lat1 + lat2) / 2;
  const dLon = lon2 - lon1;
  const dLat = lat2 - lat1;
  const dist = Math.sqrt(dLon * dLon + dLat * dLat);
  const perpOffset = Math.min(dist * 0.15, 1.5);
  const angle = Math.atan2(dLat, dLon);
  const cpLon = midLon + Math.cos(angle + Math.PI / 2) * perpOffset;
  const cpLat = midLat + Math.sin(angle + Math.PI / 2) * perpOffset;
  const steps = 20;
  const coords: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const t1 = 1 - t;
    coords.push([t1 * t1 * lon1 + 2 * t1 * t * cpLon + t * t * lon2, t1 * t1 * lat1 + 2 * t1 * t * cpLat + t * t * lat2]);
  }
  return {
    type: "Feature",
    geometry: { type: "LineString", coordinates: coords },
    properties: {
      source_name: plant.n,
      destination_name: dest.name,
      destination_type: dest.type,
      distance_km: dest.distanceKm,
      estimated: true,
    },
  };
}

export function buildFlowGeoJSON(
  plant: PowerPlant,
  destinations: EnergyFactoryDestination[],
): GeoJSON.FeatureCollection {
  const features = destinations.map((d) => buildFlowLine(plant, d));
  return { type: "FeatureCollection", features };
}
