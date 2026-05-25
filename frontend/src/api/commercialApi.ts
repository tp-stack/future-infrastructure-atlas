export type CommercialApiMethod = "GET" | "POST";

export interface CommercialApiConfig {
  baseUrl: string;
  apiKey: string;
}

export interface CommercialApiError {
  code: string;
  message: string;
  status: number;
}

export interface SourceAttribution {
  source_key: string;
  source_name: string;
  license: string;
  url?: string | null;
  attribution_required: boolean;
  terms_url?: string | null;
}

export interface CommercialAsset {
  asset_id: string;
  asset_type: string;
  asset_subtype?: string | null;
  canonical_name?: string | null;
  raw_name?: string | null;
  country_iso2?: string | null;
  confidence?: number | null;
  sensitivity_level: string;
  geometry_precision: string;
  geometry?: GeoJSON.Geometry | null;
  properties: Record<string, unknown>;
  source: SourceAttribution;
}

export interface AssetListResponse {
  data: CommercialAsset[];
  next_cursor?: string | null;
  attribution: SourceAttribution[];
}

export interface AssetDetailResponse {
  data: CommercialAsset;
  attribution: SourceAttribution[];
}

export interface RegionScoreRecord {
  score_id: string;
  region_id: string;
  region_type: string;
  score_model_version: string;
  final_score?: number | null;
  confidence?: number | null;
  geometry?: GeoJSON.Geometry | null;
}

export interface RegionScoreResponse {
  data: RegionScoreRecord[];
  next_cursor?: string | null;
}

export interface TileCatalogLayer {
  layer_id: string;
  tile_format: string;
  tilejson_url: string;
  attribution: SourceAttribution[];
}

export interface TileCatalogResponse {
  layers: TileCatalogLayer[];
}

export interface TileJSONResponse {
  tilejson: string;
  name: string;
  format: string;
  tiles: string[];
  attribution: string;
  vector_layers: Array<Record<string, unknown>>;
}

export interface ExportJobResponse {
  export_job_id: string;
  status: string;
  format: string;
  requested_layers: string[];
  row_count?: number | null;
  size_bytes?: number | null;
  signed_url?: string | null;
  error_message?: string | null;
}

export interface BillingPlanRecord {
  plan_key: string;
  display_name: string;
  price_monthly_cents: number;
  monthly_request_quota: number;
  monthly_export_quota_mb: number;
  max_export_rows: number;
  included_export_jobs: number;
  extra_extraction_cents: number;
  allowed_scopes: string[];
  stripe_price_configured: boolean;
}

export interface BillingPlanCatalogResponse {
  plans: BillingPlanRecord[];
}

export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
  plan: string;
}

export interface RequestResult<T> {
  ok: boolean;
  status: number;
  url: string;
  data?: T;
  error?: CommercialApiError;
  elapsedMs: number;
}

export function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, "");
}

export function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  }
  const value = query.toString();
  return value ? `?${value}` : "";
}

export async function commercialApiRequest<T>(
  config: CommercialApiConfig,
  path: string,
  options: { method?: CommercialApiMethod; body?: unknown; apiKeyRequired?: boolean } = {},
): Promise<RequestResult<T>> {
  const baseUrl = normalizeBaseUrl(config.baseUrl);
  const url = `${baseUrl}${path}`;
  const started = performance.now();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.apiKeyRequired !== false && config.apiKey.trim()) {
    headers["X-API-Key"] = config.apiKey.trim();
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
    const elapsedMs = Math.round(performance.now() - started);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
      const detail = typeof payload === "object" && payload && "detail" in payload
        ? (payload as { detail?: { code?: string; message?: string } }).detail
        : null;
      return {
        ok: false,
        status: response.status,
        url,
        elapsedMs,
        error: {
          code: detail?.code || `http_${response.status}`,
          message: detail?.message || (typeof payload === "string" ? payload : response.statusText),
          status: response.status,
        },
      };
    }

    return { ok: true, status: response.status, url, elapsedMs, data: payload as T };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      url,
      elapsedMs: Math.round(performance.now() - started),
      error: {
        code: "network_error",
        message: error instanceof Error ? error.message : "Network request failed.",
        status: 0,
      },
    };
  }
}
