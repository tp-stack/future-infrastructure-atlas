import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type AssetDetailResponse,
  type AssetListResponse,
  type CheckoutSessionResponse,
  type CommercialApiConfig,
  type ExportJobResponse,
  type RegionScoreResponse,
  type RequestResult,
  type SourceAttribution,
  type TileCatalogLayer,
  type TileCatalogResponse,
  type TileJSONResponse,
  buildQuery,
  commercialApiRequest,
  normalizeBaseUrl,
} from "../api/commercialApi";

type ApiTab = "assets" | "tiles" | "exports" | "pricing" | "sources" | "docs";
type ConnectionState = "idle" | "checking" | "online" | "offline";

interface CommercialApiConsoleProps {
  embedded?: boolean;
  onClose?: () => void;
  initialTab?: ApiTab;
}

interface PricingTier {
  key: "launch" | "scale" | "enterprise";
  name: string;
  price: string;
  cadence: string;
  audience: string;
  included: string[];
  extraction: string;
  overage: string;
}

const STORAGE_BASE_URL = "commercial-api-base-url";
const STORAGE_API_KEY = "commercial-api-key";
const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
const PRICING_TIERS: PricingTier[] = [
  {
    key: "launch",
    name: "Launch",
    price: "$299",
    cadence: "per month",
    audience: "Prototype users and small research teams",
    included: ["25k API requests", "500k tile requests", "5 exports up to 50k rows each", "CSV and GeoJSON exports"],
    extraction: "$49 per extra extraction",
    overage: "$0.002 per additional record",
  },
  {
    key: "scale",
    name: "Scale",
    price: "$1,250",
    cadence: "per month",
    audience: "Commercial teams building recurring workflows",
    included: ["250k API requests", "5M tile requests", "50 exports up to 500k rows each", "CSV, GeoJSON, and Parquet exports"],
    extraction: "$149 per extra extraction",
    overage: "$0.001 per additional record",
  },
  {
    key: "enterprise",
    name: "Enterprise",
    price: "$4,900+",
    cadence: "per month",
    audience: "Data resale, model enrichment, and bulk procurement",
    included: ["2M API requests", "50M tile requests", "500 exports with negotiated caps", "Dedicated commercial rights review"],
    extraction: "Custom bulk extraction pricing",
    overage: "Contracted usage bands",
  },
];

function formatMs(ms: number | null): string {
  if (ms === null) return "No request";
  return `${ms.toLocaleString()} ms`;
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function compactJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function endpointSnippet(baseUrl: string, path: string, method = "GET", body?: unknown): string {
  const lines = [
    `curl -X ${method} "${normalizeBaseUrl(baseUrl)}${path}"`,
    `  -H "X-API-Key: $FIA_API_KEY"`,
    `  -H "Accept: application/json"`,
  ];
  if (body !== undefined) {
    lines.push(`  -H "Content-Type: application/json"`);
    lines.push(`  -d '${JSON.stringify(body)}'`);
  }
  return lines.join(" \\\n");
}

function resultStatus(result: RequestResult<unknown> | null): { label: string; tone: string } {
  if (!result) return { label: "Idle", tone: "neutral" };
  if (result.ok) return { label: `${result.status} OK`, tone: "ok" };
  if (result.status === 0) return { label: "Network", tone: "bad" };
  if (result.status === 401 || result.status === 403) return { label: `${result.status} Auth`, tone: "warn" };
  return { label: `${result.status} Error`, tone: "bad" };
}

function sourceLabel(source: SourceAttribution): string {
  return `${source.source_name || source.source_key} (${source.license || "license pending"})`;
}

export default function CommercialApiConsole({ embedded = false, onClose, initialTab = "assets" }: CommercialApiConsoleProps) {
  const [baseUrl, setBaseUrl] = useState(() => sessionStorage.getItem(STORAGE_BASE_URL) || DEFAULT_BASE_URL);
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(STORAGE_API_KEY) || "");
  const [activeTab, setActiveTab] = useState<ApiTab>(initialTab);
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [lastResult, setLastResult] = useState<RequestResult<unknown> | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const [assetType, setAssetType] = useState("");
  const [country, setCountry] = useState("");
  const [bbox, setBbox] = useState("");
  const [operator, setOperator] = useState("");
  const [minConfidence, setMinConfidence] = useState("0.7");
  const [limit, setLimit] = useState("25");
  const [assetId, setAssetId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [assets, setAssets] = useState<AssetListResponse | null>(null);
  const [assetDetail, setAssetDetail] = useState<AssetDetailResponse | null>(null);
  const [scores, setScores] = useState<RegionScoreResponse | null>(null);

  const [tileCatalog, setTileCatalog] = useState<TileCatalogResponse | null>(null);
  const [selectedLayer, setSelectedLayer] = useState("");
  const [tileJson, setTileJson] = useState<TileJSONResponse | null>(null);

  const [exportFormat, setExportFormat] = useState<"geojson" | "csv" | "parquet">("csv");
  const [exportLayers, setExportLayers] = useState("commercial_power");
  const [exportJobId, setExportJobId] = useState("");
  const [exportJob, setExportJob] = useState<ExportJobResponse | null>(null);
  const [checkoutMessage, setCheckoutMessage] = useState("");

  const [attribution, setAttribution] = useState<SourceAttribution[]>([]);

  const config = useMemo<CommercialApiConfig>(() => ({ baseUrl, apiKey }), [baseUrl, apiKey]);
  const status = resultStatus(lastResult);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_BASE_URL, baseUrl);
  }, [baseUrl]);

  useEffect(() => {
    if (apiKey) sessionStorage.setItem(STORAGE_API_KEY, apiKey);
    else sessionStorage.removeItem(STORAGE_API_KEY);
  }, [apiKey]);

  const execute = useCallback(async <T,>(
    action: string,
    path: string,
    options: { method?: "GET" | "POST"; body?: unknown; apiKeyRequired?: boolean } = {},
  ): Promise<RequestResult<T>> => {
    setBusyAction(action);
    const result = await commercialApiRequest<T>(config, path, options);
    setLastResult(result as RequestResult<unknown>);
    setLastLatency(result.elapsedMs);
    setBusyAction(null);
    return result;
  }, [config]);

  const checkConnection = useCallback(async () => {
    setConnection("checking");
    const result = await execute<{ status: string }>("health", "/healthz", { apiKeyRequired: false });
    setConnection(result.ok ? "online" : "offline");
  }, [execute]);

  const runAssets = useCallback(async () => {
    const path = `/v1/assets${buildQuery({
      asset_type: assetType,
      country,
      bbox,
      operator,
      min_confidence: minConfidence,
      limit,
    })}`;
    const result = await execute<AssetListResponse>("assets", path);
    if (result.ok && result.data) {
      setAssets(result.data);
      setAssetDetail(null);
      setAttribution(result.data.attribution);
    }
  }, [assetType, bbox, country, execute, limit, minConfidence, operator]);

  const runAssetDetail = useCallback(async () => {
    if (!assetId.trim()) return;
    const result = await execute<AssetDetailResponse>("asset-detail", `/v1/assets/${encodeURIComponent(assetId.trim())}`);
    if (result.ok && result.data) {
      setAssetDetail(result.data);
      setAttribution(result.data.attribution);
    }
  }, [assetId, execute]);

  const runSearch = useCallback(async () => {
    if (searchQuery.trim().length < 2) return;
    const result = await execute<AssetListResponse>("search", `/v1/search${buildQuery({ q: searchQuery.trim(), limit })}`);
    if (result.ok && result.data) {
      setAssets(result.data);
      setAssetDetail(null);
      setAttribution(result.data.attribution);
    }
  }, [execute, limit, searchQuery]);

  const runScores = useCallback(async () => {
    const result = await execute<RegionScoreResponse>("scores", `/v1/regions/scores${buildQuery({ limit })}`);
    if (result.ok && result.data) setScores(result.data);
  }, [execute, limit]);

  const runAttribution = useCallback(async () => {
    const result = await execute<{ sources: SourceAttribution[] }>("attribution", "/v1/sources/attribution");
    if (result.ok && result.data) setAttribution(result.data.sources);
  }, [execute]);

  const runTileCatalog = useCallback(async () => {
    const result = await execute<TileCatalogResponse>("tile-catalog", "/v1/tiles/catalog");
    if (result.ok && result.data) {
      setTileCatalog(result.data);
      const firstLayer = result.data.layers[0]?.layer_id || "";
      setSelectedLayer((current) => current || firstLayer);
    }
  }, [execute]);

  const runTileJson = useCallback(async () => {
    if (!selectedLayer.trim()) return;
    const result = await execute<TileJSONResponse>("tilejson", `/v1/tiles/${encodeURIComponent(selectedLayer.trim())}/tilejson`);
    if (result.ok && result.data) setTileJson(result.data);
  }, [execute, selectedLayer]);

  const createExport = useCallback(async () => {
    const layers = exportLayers.split(",").map((layer) => layer.trim()).filter(Boolean);
    if (!layers.length) return;
    const body = { format: exportFormat, layers, filters: {} };
    const result = await execute<ExportJobResponse>("export-create", "/v1/exports", { method: "POST", body });
    if (result.ok && result.data) {
      setExportJob(result.data);
      setExportJobId(result.data.export_job_id);
    }
  }, [execute, exportFormat, exportLayers]);

  const fetchExport = useCallback(async () => {
    if (!exportJobId.trim()) return;
    const result = await execute<ExportJobResponse>("export-status", `/v1/exports/${encodeURIComponent(exportJobId.trim())}`);
    if (result.ok && result.data) setExportJob(result.data);
  }, [execute, exportJobId]);

  const copySnippet = useCallback(async (text: string) => {
    await navigator.clipboard.writeText(text);
  }, []);

  const startCheckout = useCallback(async (tier: PricingTier) => {
    setCheckoutMessage("");
    const result = await execute<CheckoutSessionResponse>("stripe-checkout", "/v1/billing/checkout", {
      method: "POST",
      apiKeyRequired: false,
      body: { plan: tier.key },
    });
    if (result.ok && result.data?.checkout_url) {
      window.location.href = result.data.checkout_url;
      return;
    }
    setCheckoutMessage(result.error?.message || `Stripe checkout could not start for ${tier.name}.`);
  }, [execute]);

  const connectionLabel = connection === "online" ? "API online" : connection === "checking" ? "Checking" : connection === "offline" ? "API offline" : "Not checked";
  const selectedTileLayer = tileCatalog?.layers.find((layer) => layer.layer_id === selectedLayer);
  const assetsEndpoint = `/v1/assets${buildQuery({
    asset_type: assetType,
    country,
    bbox,
    operator,
    min_confidence: minConfidence,
    limit,
  })}`;
  const exportBody = {
    format: exportFormat,
    layers: exportLayers.split(",").map((layer) => layer.trim()).filter(Boolean),
    filters: {},
  };

  return (
    <div className={`commercial-api-shell ${embedded ? "commercial-api-shell--embedded" : ""}`}>
      <header className="commercial-api-header">
        <div className="commercial-api-title-block">
          <span className="commercial-api-kicker">Commercial surface</span>
          <h1>FUTURE Atlas API Console</h1>
          <p>Test authenticated assets, protected tiles, exports, attribution, and commercial rights behavior from the browser.</p>
        </div>
        <div className="commercial-api-status-row">
          <span className={`api-pill api-pill--${connection === "online" ? "ok" : connection === "offline" ? "bad" : "neutral"}`}>{connectionLabel}</span>
          <span className={`api-pill api-pill--${status.tone}`}>{status.label}</span>
          <span className="api-pill api-pill--neutral">{formatMs(lastLatency)}</span>
          {onClose && (
            <button className="api-close-btn" type="button" onClick={onClose} title="Close API workbench">
              Close
            </button>
          )}
        </div>
      </header>

      <section className="api-config-strip">
        <label className="api-field api-field--wide">
          <span>API base URL</span>
          <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder={DEFAULT_BASE_URL} />
        </label>
        <label className="api-field api-field--secret">
          <span>API key</span>
          <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="fia_..." type="password" />
        </label>
        <button className="api-action api-action--primary" onClick={checkConnection} disabled={busyAction === "health"}>
          Check
        </button>
      </section>

      <nav className="api-tabs" aria-label="Commercial API sections">
        {(["assets", "tiles", "exports", "pricing", "sources", "docs"] as ApiTab[]).map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab === "assets" ? "Data API" : tab === "tiles" ? "Tile API" : tab === "exports" ? "Export API" : tab === "pricing" ? "Pricing" : tab === "sources" ? "Attribution" : "Docs"}
          </button>
        ))}
      </nav>

      <main className="commercial-api-grid">
        <section className="api-workspace">
          {activeTab === "assets" && (
            <div className="api-panel">
              <div className="api-panel-heading">
                <div>
                  <h2>Commercial Data API</h2>
                  <p>Query only records that pass the server-side rights gate.</p>
                </div>
                <div className="api-button-row">
                  <button className="api-action api-action--primary" onClick={runAssets} disabled={busyAction === "assets"}>Run assets</button>
                  <button className="api-action" onClick={runScores} disabled={busyAction === "scores"}>Scores</button>
                </div>
              </div>

              <div className="api-form-grid">
                <label className="api-field">
                  <span>Asset type</span>
                  <input value={assetType} onChange={(event) => setAssetType(event.target.value)} placeholder="power_plant" />
                </label>
                <label className="api-field">
                  <span>Country</span>
                  <input value={country} onChange={(event) => setCountry(event.target.value.toUpperCase())} placeholder="US" maxLength={2} />
                </label>
                <label className="api-field">
                  <span>Bbox</span>
                  <input value={bbox} onChange={(event) => setBbox(event.target.value)} placeholder="-125,24,-66,49" />
                </label>
                <label className="api-field">
                  <span>Operator</span>
                  <input value={operator} onChange={(event) => setOperator(event.target.value)} placeholder="operator name" />
                </label>
                <label className="api-field">
                  <span>Min confidence</span>
                  <input value={minConfidence} onChange={(event) => setMinConfidence(event.target.value)} inputMode="decimal" />
                </label>
                <label className="api-field">
                  <span>Limit</span>
                  <input value={limit} onChange={(event) => setLimit(event.target.value)} inputMode="numeric" />
                </label>
              </div>

              <div className="api-inline-tools">
                <label className="api-field">
                  <span>Asset id</span>
                  <input value={assetId} onChange={(event) => setAssetId(event.target.value)} placeholder="asset UUID" />
                </label>
                <button className="api-action" onClick={runAssetDetail} disabled={!assetId.trim() || busyAction === "asset-detail"}>Get asset</button>
                <label className="api-field">
                  <span>Search</span>
                  <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="solar, cable, city" />
                </label>
                <button className="api-action" onClick={runSearch} disabled={searchQuery.trim().length < 2 || busyAction === "search"}>Search</button>
              </div>

              <AssetResults assets={assets} assetDetail={assetDetail} scores={scores} />
            </div>
          )}

          {activeTab === "tiles" && (
            <div className="api-panel">
              <div className="api-panel-heading">
                <div>
                  <h2>Protected Tile API</h2>
                  <p>Discover entitled layers and request short-lived TileJSON URLs.</p>
                </div>
                <button className="api-action api-action--primary" onClick={runTileCatalog} disabled={busyAction === "tile-catalog"}>Load catalog</button>
              </div>
              <div className="api-inline-tools">
                <label className="api-field">
                  <span>Layer</span>
                  <input value={selectedLayer} onChange={(event) => setSelectedLayer(event.target.value)} placeholder="commercial_power" />
                </label>
                <button className="api-action" onClick={runTileJson} disabled={!selectedLayer.trim() || busyAction === "tilejson"}>Get TileJSON</button>
              </div>
              <TileCatalog layers={tileCatalog?.layers || []} selectedLayer={selectedLayer} onSelect={setSelectedLayer} />
              {selectedTileLayer && (
                <div className="api-note">
                  Selected layer attribution: {selectedTileLayer.attribution.map(sourceLabel).join("; ")}
                </div>
              )}
              {tileJson && (
                <div className="api-json-block">
                  <div className="api-json-title">TileJSON response</div>
                  <pre>{compactJson(tileJson)}</pre>
                </div>
              )}
            </div>
          )}

          {activeTab === "exports" && (
            <div className="api-panel">
              <div className="api-panel-heading">
                <div>
                  <h2>Paid Export API</h2>
                  <p>Create plan-capped jobs and poll signed download URLs.</p>
                </div>
                <button className="api-action api-action--primary" onClick={createExport} disabled={busyAction === "export-create"}>Create export</button>
              </div>
              <div className="api-form-grid api-form-grid--compact">
                <label className="api-field">
                  <span>Format</span>
                  <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "geojson" | "csv" | "parquet")}>
                    <option value="csv">CSV</option>
                    <option value="geojson">GeoJSON</option>
                    <option value="parquet">Parquet</option>
                  </select>
                </label>
                <label className="api-field api-field--wide">
                  <span>Layers</span>
                  <input value={exportLayers} onChange={(event) => setExportLayers(event.target.value)} placeholder="commercial_power,commercial_data_centers" />
                </label>
              </div>
              <div className="api-inline-tools">
                <label className="api-field">
                  <span>Export job id</span>
                  <input value={exportJobId} onChange={(event) => setExportJobId(event.target.value)} placeholder="job UUID" />
                </label>
                <button className="api-action" onClick={fetchExport} disabled={!exportJobId.trim() || busyAction === "export-status"}>Refresh job</button>
              </div>
              <ExportJob job={exportJob} />
            </div>
          )}

          {activeTab === "pricing" && (
            <div className="api-panel">
              <div className="api-panel-heading">
                <div>
                  <h2>Extraction Pricing</h2>
                  <p>Price the hosted API as recurring access plus metered extraction, not resale of unreviewed raw third-party data.</p>
                </div>
              </div>
              <PricingCards tiers={PRICING_TIERS} onCheckout={startCheckout} />
              {checkoutMessage && <div className="api-note api-note--checkout">{checkoutMessage}</div>}
              <div className="api-json-block">
                <div className="api-json-title">Stripe setup contract</div>
                <pre>{compactJson({
                  checkout_mode: "subscription",
                  product_model: "one Stripe Product per plan, one recurring Price per plan",
                  checkout_endpoint: `${normalizeBaseUrl(baseUrl)}/v1/billing/checkout`,
                  webhook_endpoint: `${normalizeBaseUrl(baseUrl)}/v1/billing/webhook`,
                  success_url: `${window.location.origin}/?commercialApi=1&checkout=success`,
                  cancel_url: `${window.location.origin}/?commercialApi=1&checkout=cancelled`,
                  metadata: ["plan_key", "customer_key", "allowed_scopes"],
                })}</pre>
              </div>
            </div>
          )}

          {activeTab === "sources" && (
            <div className="api-panel">
              <div className="api-panel-heading">
                <div>
                  <h2>Attribution and Rights Metadata</h2>
                  <p>Every commercial response carries source metadata for downstream compliance.</p>
                </div>
                <button className="api-action api-action--primary" onClick={runAttribution} disabled={busyAction === "attribution"}>Load attribution</button>
              </div>
              <AttributionList sources={attribution} />
            </div>
          )}

          {activeTab === "docs" && (
            <div className="api-panel">
              <div className="api-panel-heading">
                <div>
                  <h2>Customer Integration Notes</h2>
                  <p>Commercial clients should call the hosted API, not static browser data.</p>
                </div>
              </div>
              <div className="api-doc-grid">
                <DocItem title="Authentication" value="X-API-Key or Authorization: Bearer" />
                <DocItem title="Scopes" value="assets:read, tiles:read, exports:create" />
                <DocItem title="Rights posture" value="Fail closed; only approved commercial grants are served" />
                <DocItem title="Tile delivery" value="Catalog then short-lived signed TileJSON URL" />
              </div>
              <div className="api-json-block">
                <div className="api-json-title">Assets example</div>
                <pre>{endpointSnippet(baseUrl, assetsEndpoint)}</pre>
              </div>
              <div className="api-json-block">
                <div className="api-json-title">Export example</div>
                <pre>{endpointSnippet(baseUrl, "/v1/exports", "POST", exportBody)}</pre>
              </div>
            </div>
          )}
        </section>

        <aside className="api-inspector">
          <div className="api-inspector-card">
            <div className="api-inspector-heading">
              <span>Last request</span>
              {lastResult && <button onClick={() => copySnippet(lastResult.url)} title="Copy URL">Copy URL</button>}
            </div>
            {lastResult ? (
              <>
                <div className="api-request-url">{lastResult.url}</div>
                {lastResult.error ? (
                  <div className="api-error-box">
                    <strong>{lastResult.error.code}</strong>
                    <span>{lastResult.error.message}</span>
                  </div>
                ) : (
                  <div className="api-success-box">Response accepted by the API.</div>
                )}
              </>
            ) : (
              <div className="api-empty-state">Run a request to inspect status, latency, and errors.</div>
            )}
          </div>

          <div className="api-inspector-card">
            <div className="api-inspector-heading">
              <span>Rights gate</span>
            </div>
            <ul className="api-rights-list">
              <li>Commercial API allowed</li>
              <li>Redistribution allowed for exports</li>
              <li>Approved license review</li>
              <li>No unresolved share-alike risk</li>
              <li>Attribution present in responses</li>
            </ul>
          </div>

          <div className="api-inspector-card">
            <div className="api-inspector-heading">
              <span>{activeTab === "pricing" ? "Stripe next step" : "Current snippet"}</span>
              <button onClick={() => copySnippet(endpointSnippet(baseUrl, activeTab === "exports" ? "/v1/exports" : assetsEndpoint, activeTab === "exports" ? "POST" : "GET", activeTab === "exports" ? exportBody : undefined))}>
                Copy
              </button>
            </div>
            {activeTab === "pricing" ? (
              <div className="api-empty-state">Create Stripe Products and recurring Prices, then expose a server endpoint that creates Checkout Sessions and returns the hosted checkout URL.</div>
            ) : (
              <pre className="api-code-sample">
                {endpointSnippet(baseUrl, activeTab === "exports" ? "/v1/exports" : assetsEndpoint, activeTab === "exports" ? "POST" : "GET", activeTab === "exports" ? exportBody : undefined)}
              </pre>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}

function PricingCards({ tiers, onCheckout }: { tiers: PricingTier[]; onCheckout: (tier: PricingTier) => void }) {
  return (
    <div className="api-pricing-grid">
      {tiers.map((tier) => (
        <article className={`api-pricing-card api-pricing-card--${tier.key}`} key={tier.key}>
          <div className="api-pricing-top">
            <span>{tier.name}</span>
            <strong>{tier.price}</strong>
            <em>{tier.cadence}</em>
          </div>
          <p>{tier.audience}</p>
          <ul>
            {tier.included.map((item) => <li key={item}>{item}</li>)}
          </ul>
          <div className="api-pricing-meter">
            <span>{tier.extraction}</span>
            <small>{tier.overage}</small>
          </div>
          <button className="api-action api-action--primary" type="button" onClick={() => onCheckout(tier)}>
            Start checkout
          </button>
        </article>
      ))}
    </div>
  );
}

function AssetResults({
  assets,
  assetDetail,
  scores,
}: {
  assets: AssetListResponse | null;
  assetDetail: AssetDetailResponse | null;
  scores: RegionScoreResponse | null;
}) {
  if (assetDetail) {
    return (
      <div className="api-result-list">
        <div className="api-result-card api-result-card--featured">
          <div>
            <strong>{assetDetail.data.canonical_name || assetDetail.data.raw_name || assetDetail.data.asset_id}</strong>
            <span>{assetDetail.data.asset_type} · {assetDetail.data.country_iso2 || "global"}</span>
          </div>
          <div className="api-metric">{Math.round((assetDetail.data.confidence || 0) * 100)}%</div>
        </div>
      </div>
    );
  }

  if (assets?.data.length) {
    return (
      <div className="api-result-list">
        {assets.data.slice(0, 8).map((asset) => (
          <div className="api-result-card" key={asset.asset_id}>
            <div>
              <strong>{asset.canonical_name || asset.raw_name || asset.asset_id}</strong>
              <span>{asset.asset_type} · {asset.country_iso2 || "global"} · {asset.source.source_key}</span>
            </div>
            <div className="api-metric">{asset.confidence != null ? `${Math.round(asset.confidence * 100)}%` : "-"}</div>
          </div>
        ))}
        {assets.next_cursor && <div className="api-note">Next cursor: {assets.next_cursor}</div>}
      </div>
    );
  }

  if (scores?.data.length) {
    return (
      <div className="api-result-list">
        {scores.data.slice(0, 8).map((score) => (
          <div className="api-result-card" key={score.score_id}>
            <div>
              <strong>{score.region_id}</strong>
              <span>{score.region_type} · {score.score_model_version}</span>
            </div>
            <div className="api-metric">{score.final_score ?? "-"}</div>
          </div>
        ))}
      </div>
    );
  }

  return <div className="api-empty-state">No commercial data loaded yet.</div>;
}

function TileCatalog({
  layers,
  selectedLayer,
  onSelect,
}: {
  layers: TileCatalogLayer[];
  selectedLayer: string;
  onSelect: (layer: string) => void;
}) {
  if (!layers.length) return <div className="api-empty-state">Load the tile catalog to see entitled layers.</div>;
  return (
    <div className="api-layer-list">
      {layers.map((layer) => (
        <button key={layer.layer_id} className={selectedLayer === layer.layer_id ? "active" : ""} onClick={() => onSelect(layer.layer_id)}>
          <span>{layer.layer_id}</span>
          <em>{layer.tile_format}</em>
        </button>
      ))}
    </div>
  );
}

function ExportJob({ job }: { job: ExportJobResponse | null }) {
  if (!job) return <div className="api-empty-state">No export job created yet.</div>;
  return (
    <div className="api-export-card">
      <div>
        <strong>{job.export_job_id}</strong>
        <span>{job.requested_layers.join(", ")}</span>
      </div>
      <div className={`api-export-status api-export-status--${job.status}`}>{job.status}</div>
      <dl>
        <div><dt>Format</dt><dd>{job.format}</dd></div>
        <div><dt>Rows</dt><dd>{job.row_count ?? "-"}</dd></div>
        <div><dt>Size</dt><dd>{formatBytes(job.size_bytes)}</dd></div>
      </dl>
      {job.signed_url && <a href={job.signed_url} target="_blank" rel="noreferrer">Open signed download</a>}
      {job.error_message && <div className="api-error-box"><strong>Rejected</strong><span>{job.error_message}</span></div>}
    </div>
  );
}

function AttributionList({ sources }: { sources: SourceAttribution[] }) {
  if (!sources.length) return <div className="api-empty-state">No attribution loaded yet.</div>;
  return (
    <div className="api-source-list">
      {sources.map((source) => (
        <div className="api-source-row" key={source.source_key}>
          <div>
            <strong>{source.source_name}</strong>
            <span>{source.source_key} · {source.license}</span>
          </div>
          <span className={`api-pill api-pill--${source.attribution_required ? "warn" : "ok"}`}>
            {source.attribution_required ? "Attribution required" : "No attribution required"}
          </span>
        </div>
      ))}
    </div>
  );
}

function DocItem({ title, value }: { title: string; value: string }) {
  return (
    <div className="api-doc-item">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}
