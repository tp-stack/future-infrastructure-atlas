import type { CandidateSite } from "../api/siteSelectionApi";

export function buildSuitabilityHeatmapGeoJSON(candidates: CandidateSite[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: candidates
      .filter((c) => !c.excluded)
      .map((c) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [c.lon, c.lat],
        },
        properties: {
          score: c.final_score,
          weight: c.final_score / 100,
        },
      })),
  };
}

export function getSuitabilityHeatmapLayerId(): string {
  return "suitability-heatmap-layer";
}

export function getSuitabilityHeatmapSourceId(): string {
  return "suitability-heatmap-source";
}
