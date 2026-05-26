export interface ComputeProfile {
  key: string;
  name: string;
  description: string;
  min_power_mw: number;
  preferred_area_ha: number;
  max_substation_distance_km: number;
  max_fiber_distance_km: number;
  latency_priority: string;
  grid_priority: string;
  regulatory_priority: string;
  typical_use_case: string;
}

export interface ScoringProfile {
  key: string;
  name: string;
  description: string;
  weights: Record<string, number>;
}

export interface ProfilesResponse {
  compute_profiles: ComputeProfile[];
  scoring_profiles: ScoringProfile[];
}

export interface CandidateSite {
  rank: number;
  candidate_site_id: string;
  lat: number;
  lon: number;
  country: string;
  region: string;
  municipality: string;
  area_ha: number;
  compute_profile: string;
  final_score: number;
  confidence_score: number;
  grid_score: number;
  fiber_score: number;
  land_score: number;
  climate_score: number;
  water_score: number;
  regulatory_score: number;
  market_score: number;
  incentive_score: number;
  missing_data_flags: string[];
  human_review_required: boolean;
  evidence_summary: string;
  excluded: boolean;
  exclusion_reasons: string[];
  soft_constraints: string[];
  nearest_substation_km: number | null;
  nearest_fiber_km: number | null;
  nearest_ixp_km: number | null;
  estimated_grid_capacity_mw: number | null;
  flood_risk_score: number | null;
  water_stress_score: number | null;
  regulatory_stability_score: number | null;
}

export interface QueryResponse {
  candidates: CandidateSite[];
  count: number;
  profile: string;
  scoring_profile: string;
  area: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface QueryArea {
  type: "bbox";
  coordinates: [number, number, number, number];
}

export async function fetchProfiles(baseUrl: string): Promise<ProfilesResponse> {
  const res = await fetch(`${baseUrl}/v1/site-selection/profiles`);
  if (!res.ok) throw new Error(`Failed to fetch profiles: ${res.statusText}`);
  return res.json();
}

export async function queryCandidates(
  baseUrl: string,
  area: QueryArea,
  profile: string,
  scoringProfile: string,
  limit: number,
  includeExcluded: boolean,
): Promise<QueryResponse> {
  const res = await fetch(`${baseUrl}/v1/site-selection/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      area: { type: area.type, coordinates: area.coordinates },
      profile,
      scoring_profile: scoringProfile,
      limit,
      include_excluded: includeExcluded,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Query failed: ${res.statusText}`);
  }
  return res.json();
}
