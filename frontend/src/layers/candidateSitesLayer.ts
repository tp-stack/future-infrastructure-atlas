import type { CandidateSite } from "../api/siteSelectionApi";

export function buildCandidateSitesGeoJSON(candidates: CandidateSite[]): GeoJSON.FeatureCollection {
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
          id: c.candidate_site_id,
          rank: c.rank,
          score: c.final_score,
          confidence: c.confidence_score,
          country: c.country,
          region: c.region,
          humanReviewRequired: c.human_review_required,
        },
      })),
  };
}

export function getCandidateSitePaint(scoreProperty: string = "score"): maplibregl.CircleLayerSpecification["paint"] {
  return {
    "circle-radius": 8,
    "circle-color": [
      "case",
      [">=", ["get", scoreProperty], 80],
      "#22c55e",
      [">=", ["get", scoreProperty], 60],
      "#d69a13",
      [">=", ["get", scoreProperty], 40],
      "#f59e0b",
      "#ef4444",
    ],
    "circle-opacity": 0.85,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#ffffff",
  };
}

export function getCandidateSiteLayerId(): string {
  return "candidate-sites-layer";
}

export function getCandidateSiteSourceId(): string {
  return "candidate-sites-source";
}
