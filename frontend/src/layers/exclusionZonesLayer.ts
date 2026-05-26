import type { CandidateSite } from "../api/siteSelectionApi";

export function buildExclusionZonesGeoJSON(candidates: CandidateSite[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: candidates
      .filter((c) => c.excluded)
      .map((c) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [c.lon, c.lat],
        },
        properties: {
          id: c.candidate_site_id,
          rank: c.rank,
          reasons: c.exclusion_reasons.join("; "),
        },
      })),
  };
}

export function getExclusionZonesPaint(): maplibregl.CircleLayerSpecification["paint"] {
  return {
    "circle-radius": 10,
    "circle-color": "#ef4444",
    "circle-opacity": 0.4,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#dc2626",
  };
}

export function getExclusionZonesLayerId(): string {
  return "exclusion-zones-layer";
}

export function getExclusionZonesSourceId(): string {
  return "exclusion-zones-source";
}
