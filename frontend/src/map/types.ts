export interface PowerPlant {
  n: string;
  c: string;
  f: string;
  mw: number;
  lat: number;
  lon: number;
}

export interface UnmappedRecord {
  n: string;
  source: string;
}

export interface UnmappedCable extends UnmappedRecord {
  operators: string;
  landing_points: string;
  length_km: string;
}

export interface UnmappedDataCenter {
  n: string;
  op: string;
  c: string;
  address: string;
  mw: number | null;
  source: string;
}

export interface AtlasCounts {
  power_plants_total?: number;
  power_plants_mapped: number;
  power_plants_rejected: number;
  submarine_cables_total: number;
  submarine_cables_mapped: number;
  submarine_cables_unmapped: number;
  cables_total?: number;
  cables_mapped?: number;
  cables_unmapped?: number;
  data_centers_total: number;
  data_centers_mapped: number;
  data_centers_unmapped: number;
}

export interface LayerInfo {
  key: string;
  name: string;
  dotColor: string;
  mapped: number;
  total: number;
  status: "mapped" | "metadata_only" | "missing_geometry" | "disabled";
  tooltip: string;
}

export interface AtlasMetadata {
  generated_at: string;
  sources: { key: string; name: string; url: string; license: string }[];
  disclaimer: string;
  counts: AtlasCounts;
  unmapped: {
    submarine_cables: UnmappedCable[];
    data_centers: UnmappedDataCenter[];
  };
}

export interface AtlasData {
  metadata: AtlasMetadata;
  power_plants: PowerPlant[];
  cables: { n: string; source: string; geometry: number[][] }[];
  data_centers: { n: string; op: string; c: string; city: string; lat: number; lon: number; source: string }[];
}

export type FilterState = {
  fuelType: string;
  country: string;
  minMw: number;
};

export interface ActiveFilterSummary {
  fuelType: boolean;
  country: boolean;
  minMw: boolean;
}
