import { useState, useEffect, useMemo, useCallback } from "react";
import AtlasMap from "./map/AtlasMap";
import LayerPanel from "./components/LayerPanel";
import Legend from "./components/Legend";
import SourcePanel from "./components/SourcePanel";
import StatsPanel from "./components/StatsPanel";
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
    fetch("/data/atlas_web_data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: AtlasData) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
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

  const handleToggle = useCallback((key: string) => {
    setVisibleLayers((prev) => ({ ...prev, [key]: !(prev as Record<string, boolean>)[key] }));
  }, []);

  if (loading) {
    return (
      <div className="app" style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#71717a", fontSize: 14 }}>Loading infrastructure atlas...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="app" style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#ef5350", fontSize: 14 }}>
          {error ? `Error loading data: ${error}` : "No data available"}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="side-panel">
        <div className="panel-header">
          <h1>FUTURE Infrastructure Atlas</h1>
          <div className="subtitle">Global Energy &amp; Digital Infrastructure</div>
        </div>
        <LayerPanel
          visibleLayers={visibleLayers}
          onToggle={handleToggle}
          filters={filters}
          onFilterChange={setFilters}
          fuelTypes={fuelTypes}
          countries={countries}
        />
        <Legend />
        <StatsPanel metadata={data.metadata} />
        <AssetPopup plant={selectedPlant} />
        <SourcePanel metadata={data.metadata} />
        <div className="status-bar">
          Generated {new Date(data.metadata.generated_at).toLocaleDateString()}
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
