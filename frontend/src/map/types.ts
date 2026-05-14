export interface PowerPlant {
  n: string;
  c: string;
  f: string;
  mw: number;
  lat: number;
  lon: number;
  mapped_status?: "mapped";
}

export type CableGeometry = number[][] | number[][][];

export interface Cable {
  n: string;
  source: string;
  geometry: CableGeometry;
  geometry_precision?: string;
  mapped_status: "mapped" | "unmapped";
  coordinate_source?: string;
  source_license?: string;
  source_url?: string;
  confidence?: number;
  operators?: string;
  landing_points?: string;
  length_km?: string;
  unmapped_reason?: string;
}

export interface DataCenter {
  id?: string;
  n: string;
  op: string;
  c: string;
  city: string;
  lat: number;
  lon: number;
  mw?: number | null;
  source: string;
  coordinate_precision?: string;
  mapped_status: "mapped" | "unmapped";
  coordinate_source?: string;
  source_license?: string;
  source_url?: string;
  confidence?: number;
  address?: string;
  unmapped_reason?: string;
  net_count?: number;
  ix_count?: number;
}

export type Asset = PowerPlant | Cable | DataCenter;

export interface UnmappedRecord {
  n: string;
  source: string;
}

export interface UnmappedCable extends UnmappedRecord {
  operators: string;
  landing_points: string;
  length_km: string;
  unmapped_reason: string;
}

export interface UnmappedDataCenter {
  n: string;
  op: string;
  c: string;
  address: string;
  mw: number | null;
  source: string;
  unmapped_reason: string;
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
  cable_geometry_source?: string;
  cable_geometry_license_status?: string;
  cable_geometry_review_required?: boolean;
  data_center_source?: string;
  data_center_license_status?: string;
  data_center_review_required?: boolean;
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
  cables: Cable[];
  data_centers: DataCenter[];
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

export interface AtlasCore {
  generated_at: string;
  architecture: string;
  counts: Record<string, unknown>;
  sources: { key: string; name: string; url: string; license: string }[];
  disclaimer: string;
  tile_registry: Record<string, { url: string; status: string; layer_name: string }>;
  license_warnings: { layer: string; message: string; active: boolean }[];
  data_gaps: Record<string, unknown>;
}
