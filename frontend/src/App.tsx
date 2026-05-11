import { useState, useEffect, useMemo, useCallback } from "react";
import AtlasMap from "./map/AtlasMap";
import type { CanvasDiagnostics } from "./map/InfrastructureCanvasOverlay";
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
  const [canvasDiag, setCanvasDiag] = useState<CanvasDiagnostics | null>(null);
  const [showTestPoints, setShowTestPoints] = useState(false);
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
    const s = new Set<string>();
    for (const p of data.power_plants) if (p.f) s.add(p.f);
    return Array.from(s).sort();
  }, [data]);

  const countries = useMemo(() => {
    if (!data) return [];
    const s = new Set<string>();
    for (const p of data.power_plants) if (p.c) s.add(p.c);
    return Array.from(s).sort();
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

  const activeFilterCount = useMemo(
    () => [filters.fuelType, filters.country, filters.minMw > 0 ? `${filters.minMw}+ MW` : ""].filter(Boolean).length,
    [filters]
  );

  const handleToggle = useCallback((key: string) => {
    setVisibleLayers((prev) => ({ ...prev, [key]: !(prev as Record<string, boolean>)[key] }));
  }, []);

  const hasZeroCanvasPoints = canvasDiag && data && canvasDiag.powerPlantsDrawn === 0 && canvasDiag.recordsReceived > 1000;

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
          <div className="error-footer"><SourcePanel metadata={null} /></div>
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
          <DiagnosticsPanel canvasDiag={canvasDiag} showTestPoints={showTestPoints} onToggleTestPoints={setShowTestPoints} />
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
              {hasCoverageWarning && <span className="top-bar-warning-badge">Partial coverage</span>}
              {canvasDiag && canvasDiag.projectionMode && <span className="top-bar-stat">{canvasDiag.projectionMode}</span>}
              {hasZeroCanvasPoints && <span className="top-bar-warning-badge">0 points drawn</span>}
            </div>
          </div>

          {hasCoverageWarning && (
            <div className="coverage-warning">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01M12 2l10 18H2L12 2z"/></svg>
              <span>Some infrastructure layers have limited mapped coverage. Cables: {cablesMapped}/{cablesTotal} mapped. Data centers: {dcsMapped}/{dcsTotal} mapped.</span>
            </div>
          )}

          {hasZeroCanvasPoints && (
            <div className="coverage-warning" style={{ borderTop: "1px solid rgba(200,50,50,0.2)" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v2m0 4h.01M12 2l10 18H2L12 2z"/></svg>
              <span>Data loaded ({canvasDiag?.recordsReceived?.toLocaleString()} records, {canvasDiag?.validCoords?.toLocaleString()} valid coords) but renderer drew 0 points.</span>
            </div>
          )}

          <AtlasMap
            data={data}
            filters={filters}
            visibleLayers={visibleLayers}
            onPopup={setSelectedAsset}
            onCanvasDiagnostics={setCanvasDiag}
            showTestPoints={showTestPoints}
          />
        </div>
      </div>
    </ErrorBoundary>
  );
}

function DiagnosticsPanel({
  canvasDiag,
  showTestPoints,
  onToggleTestPoints,
}: {
  canvasDiag: CanvasDiagnostics | null;
  showTestPoints: boolean;
  onToggleTestPoints: (v: boolean) => void;
}) {
  if (!canvasDiag) return null;
  return (
    <div className="panel-section">
      <h2>Renderer Diagnostics</h2>
      <div className="diag-summary">
        <div className="diag-row">
          <span className="diag-label">Canvas active</span>
          <span className={`diag-val ${canvasDiag.active ? "ok" : "fail"}`}>
            {canvasDiag.active ? "yes" : "no"}
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Canvas size</span>
          <span className="diag-val">{canvasDiag.canvasWidth} &times; {canvasDiag.canvasHeight}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Records received</span>
          <span className="diag-val">{canvasDiag.recordsReceived.toLocaleString()}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Valid coords</span>
          <span className={`diag-val ${canvasDiag.validCoords > 1000 ? "ok" : "fail"}`}>
            {canvasDiag.validCoords.toLocaleString()}
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Power plants drawn</span>
          <span className={`diag-val ${canvasDiag.powerPlantsDrawn > 1000 ? "ok" : "fail"}`}>
            {canvasDiag.powerPlantsDrawn.toLocaleString()}
          </span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Cables drawn</span>
          <span className="diag-val">{canvasDiag.cableLinesDrawn}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Data centers drawn</span>
          <span className="diag-val">{canvasDiag.dataCentersDrawn}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Test points drawn</span>
          <span className="diag-val">{canvasDiag.testPointsDrawn}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Projection</span>
          <span className="diag-val">{canvasDiag.projectionMode}</span>
        </div>
        <div className="diag-row">
          <span className="diag-label">Last draw</span>
          <span className="diag-val">{new Date(canvasDiag.lastDrawTime).toLocaleTimeString()}</span>
        </div>
        {canvasDiag.lastError && (
          <div className="diag-row">
            <span className="diag-label">Error</span>
            <span className="diag-val fail">{canvasDiag.lastError}</span>
          </div>
        )}
        <div className="diag-row">
          <span className="diag-label">Test mode</span>
          <span className="diag-val">
            <label style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
              <input type="checkbox" checked={showTestPoints} onChange={(e) => onToggleTestPoints(e.target.checked)} style={{ accentColor: "#d69a13", width: 11, height: 11 }} />
              <span style={{ color: "#8d93a1", fontSize: 9 }}>5 test cities</span>
            </label>
          </span>
        </div>
      </div>
    </div>
  );
}
