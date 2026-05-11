import { useState, useEffect, useMemo, useCallback } from "react";
import AtlasMap from "./map/AtlasMap";
import LayerPanel from "./components/LayerPanel";
import Legend from "./components/Legend";
import SourcePanel from "./components/SourcePanel";
import StatsPanel from "./components/StatsPanel";
import UnmappedPanel from "./components/UnmappedPanel";
import AssetPopup from "./components/AssetPopup";
import type { AtlasData, FilterState, PowerPlant } from "./map/types";

export default function App() {
  const [data, setData] = useState<AtlasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
  const [selectedPlant, setSelectedPlant] = useState<PowerPlant | null>(null);

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

  const handleToggle = useCallback((key: string) => {
    setVisibleLayers((prev) => ({ ...prev, [key]: !(prev as Record<string, boolean>)[key] }));
  }, []);

  if (loading) {
    return (
      <div className="app">
        <div className="loading-screen">
          <div className="loading-spinner" />
          <div className="loading-text">Loading infrastructure atlas...</div>
          <div className="loading-sub">FUTURE Infrastructure Atlas — Global energy, internet and compute infrastructure intelligence</div>
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

  const hasMappableLayers =
    data.power_plants.length > 0 ||
    data.cables.some((c) => c.geometry && c.geometry.length >= 2) ||
    data.data_centers.some((d) => d.lat != null && d.lon != null);

  return (
    <div className="app">
      <div className="side-panel">
        <div className="panel-header">
          <h1>FUTURE Infrastructure Atlas</h1>
          <div className="subtitle">Global energy, internet and compute infrastructure intelligence</div>
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
        <AssetPopup plant={selectedPlant} />
        <SourcePanel metadata={data.metadata} />
        <div className="status-bar">
          Generated {new Date(data.metadata.generated_at).toLocaleString()} — {data.power_plants.length.toLocaleString()} power plants mapped
        </div>
      </div>
      <AtlasMap
        data={data}
        filters={filters}
        visibleLayers={visibleLayers}
        onPopup={setSelectedPlant}
      />
    </div>
  );
}
