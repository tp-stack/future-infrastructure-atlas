import { useState, useEffect, useMemo, useCallback } from "react";
import AtlasMap from "./map/AtlasMap";
import type { MapDiagnostics } from "./map/AtlasMap";
import ErrorBoundary from "./components/ErrorBoundary";
import LayerPanel from "./components/LayerPanel";
import Legend from "./components/Legend";
import SourcePanel from "./components/SourcePanel";
import StatsPanel from "./components/StatsPanel";
import UnmappedPanel from "./components/UnmappedPanel";
import AssetPopup from "./components/AssetPopup";
import type { AtlasData, FilterState, Asset } from "./map/types";

export default function App() {
  const [data, setData] = useState<AtlasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [diagnostics, setDiagnostics] = useState<MapDiagnostics | null>(null);
  const [visibleLayers, setVisibleLayers] = useState({
    power_plants: true,
    cables: true,
    data_centers: true,
  });
  const [filters, setFilters] = useState<FilterState>({
    fuelType: "",
    country: "",
    minMw: 0,
  });
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/atlas_web_data.json", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}${r.status === 404 ? " — file not found" : ""}`);
        return r.json();
      })
      .then((d: AtlasData) => {
        if (!d.metadata || !d.power_plants) {
          throw new Error("Invalid data structure: missing metadata or power_plants");
        }
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const fuelTypes = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    for (const p of data.power_plants) {
      if (p.f) set.add(p.f);
    }
    return Array.from(set).sort();
  }, [data]);

  const countries = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    for (const p of data.power_plants) {
      if (p.c) set.add(p.c);
    }
    return Array.from(set).sort();
  }, [data]);

  const visibleCount = useMemo(() => {
    if (!data) return 0;
    return data.power_plants.filter((p) => {
      if (filters.fuelType && p.f !== filters.fuelType) return false;
      if (filters.country && p.c !== filters.country) return false;
      if (filters.minMw > 0 && p.mw < filters.minMw) return false;
      return true;
    }).length;
  }, [data, filters]);

  const activeFilterCount = useMemo(() => {
    return [filters.fuelType, filters.country, filters.minMw > 0 ? `${filters.minMw}+ MW` : ""].filter(Boolean).length;
  }, [filters]);

  const handleToggle = useCallback((key: string) => {
    setVisibleLayers((prev) => ({ ...prev, [key]: !(prev as Record<string, boolean>)[key] }));
  }, []);

  if (loading) {
    return (
      <div className="app">
        <div className="loading-screen">
          <div className="loading-spinner" />
          <div className="loading-text">Loading infrastructure atlas...</div>
          <div className="loading-sub">Global Infrastructure Atlas — energy, internet &amp; compute intelligence</div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="app">
        <div className="error-screen">
          <div className="error-icon">!</div>
          <div className="error-title">Data file missing or invalid</div>
          <div className="error-message">{error || "No data available"}</div>
          <div className="error-hint">Ensure atlas_web_data.json exists in the public data directory and is valid JSON.</div>
          <div className="error-footer">
            <SourcePanel metadata={null} />
          </div>
        </div>
      </div>
    );
  }

  const counts = data.metadata.counts;
  const cablesMapped = counts.cables_mapped ?? counts.submarine_cables_mapped;
  const cablesTotal = counts.cables_total ?? counts.submarine_cables_total;
  const dcsMapped = counts.data_centers_mapped;
  const dcsTotal = counts.data_centers_total;
  const hasCoverageWarning = cablesMapped < cablesTotal || dcsMapped < dcsTotal;

  return (
    <ErrorBoundary>
      <div className="app">
        <div className={`side-panel ${sidebarOpen ? "open" : "closed"}`}>
          <div className="panel-header">
            <div className="panel-header-top">
              <h1>Global Infrastructure Atlas</h1>
              <button className="sidebar-toggle" onClick={() => setSidebarOpen(false)} title="Close sidebar">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div className="panel-subtitle">Energy, internet &amp; compute intelligence</div>
          </div>
          <LayerPanel
            visibleLayers={visibleLayers}
            onToggle={handleToggle}
            filters={filters}
            onFilterChange={setFilters}
            fuelTypes={fuelTypes}
            countries={countries}
            counts={data.metadata.counts}
            visibleCount={visibleCount}
          />
          <Legend />
          <StatsPanel metadata={data.metadata} />
          <UnmappedPanel metadata={data.metadata} />
          <AssetPopup asset={selectedAsset} />
          <DiagnosticsPanel diagnostics={diagnostics} />
          <SourcePanel metadata={data.metadata} />
          <div className="panel-footer">
            Generated {new Date(data.metadata.generated_at).toLocaleString()}
          </div>
        </div>

        {!sidebarOpen && (
          <button className="sidebar-reopen" onClick={() => setSidebarOpen(true)} title="Open sidebar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
          </button>
        )}

        <div className="map-area">
          <div className="top-bar">
            <div className="top-bar-left">
              <span className="top-bar-title">Global Infrastructure Atlas</span>
              <span className="top-bar-stat">{data.power_plants.length.toLocaleString()} power plants</span>
              <span className="top-bar-stat">{cablesMapped.toLocaleString()} / {cablesTotal.toLocaleString()} cables</span>
              <span className="top-bar-stat">{dcsMapped.toLocaleString()} / {dcsTotal.toLocaleString()} data centers</span>
            </div>
            <div className="top-bar-right">
              {activeFilterCount > 0 && (
                <span className="top-bar-filter-badge">{activeFilterCount} filter{activeFilterCount > 1 ? "s" : ""} active</span>
              )}
              {hasCoverageWarning && (
                <span className="top-bar-warning-badge">Partial coverage</span>
              )}
              {diagnostics && diagnostics.status !== "ok" && (
                <span className="top-bar-warning-badge">Map: {diagnostics.status}</span>
              )}
            </div>
          </div>

          {hasCoverageWarning && (
            <div className="coverage-warning">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01M12 2l10 18H2L12 2z"/></svg>
              <span>Some infrastructure layers have limited mapped coverage. Cables: {cablesMapped}/{cablesTotal} mapped. Data centers: {dcsMapped}/{dcsTotal} mapped.</span>
            </div>
          )}

          <AtlasMap
            data={data}
            filters={filters}
            visibleLayers={visibleLayers}
            onPopup={setSelectedAsset}
            onDiagnostics={setDiagnostics}
          />
        </div>
      </div>
    </ErrorBoundary>
  );
}

function DiagnosticsPanel({ diagnostics }: { diagnostics: MapDiagnostics | null }) {
  if (!diagnostics) return null;
  return (
    <div className="panel-section">
      <h2>Map Diagnostics</h2>
      <div className="diag-summary">
        <div className="diag-row">
          <span className="diag-label">Basemap</span>
          <span className="diag-val">{diagnostics.basemap}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Layers loaded</span>
          <span className="diag-val ok">{diagnostics.layers_ok.length}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Layers failed</span>
          <span className={`diag-val ${diagnostics.layers_failed.length > 0 ? "fail" : "ok"}`}>
            {diagnostics.layers_failed.length}
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Map status</span>
          <span className={`diag-val ${diagnostics.status === "ok" ? "ok" : "fail"}`}>
            {diagnostics.status}
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Data points</span>
          <span className="diag-val">{diagnostics.total_points.toLocaleString()}</span>
        </div>
        {diagnostics.data_bounds && (
          <div className="diag-row">
            <span className="diag-label">Data bounds</span>
            <span className="diag-val">{diagnostics.data_bounds}</span>
          </div>
        )}
        {diagnostics.layers_failed.length > 0 && (
          <div style={{ marginTop: 6 }}>
            <div style={{ fontSize: 9, color: "#d07070", fontWeight: 600 }}>Failed layers:</div>
            {diagnostics.layers_failed.map((f, i) => (
              <div key={i} className="diag-row">
                <span className="diag-label">{f.layer}</span>
                <span className="diag-val fail">{f.error}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
