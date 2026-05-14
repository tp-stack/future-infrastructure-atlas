import type { FilterState, AtlasCounts } from "../map/types";
import { CABLE_COLOR, DATA_CENTER_COLOR } from "../map/layers";

interface Props {
  visibleLayers: Record<string, boolean>;
  onToggle: (key: string) => void;
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  fuelTypes: string[];
  countries: string[];
  counts: AtlasCounts | null;
  visibleCount: number;
}

type LayerConfig = {
  key: string;
  label: string;
  dotColor: string;
  getMapped: (c: AtlasCounts) => number;
  getTotal: (c: AtlasCounts) => number;
  getCoverage: (mapped: number, total: number) => "ok" | "warning" | "disabled";
  tooltip: string;
};

const LAYER_CONFIG: LayerConfig[] = [
  {
    key: "power_plants",
    label: "Power Plants",
    dotColor: "#d69a13",
    getMapped: (c: AtlasCounts) => c.power_plants_mapped,
    getTotal: (c: AtlasCounts) => c.power_plants_total ?? c.power_plants_mapped + c.power_plants_rejected,
    getCoverage: (mapped) => mapped > 0 ? "ok" : "disabled",
    tooltip: "34,936 power plants mapped from WRI Global Power Plant Database",
  },
  {
    key: "cables",
    label: "Submarine Cables",
    dotColor: CABLE_COLOR,
    getMapped: (c: AtlasCounts) => c.cables_mapped ?? c.submarine_cables_mapped,
    getTotal: (c: AtlasCounts) => c.cables_total ?? c.submarine_cables_total,
    getCoverage: (mapped, total) => {
      if (mapped === 0) return "disabled";
      return mapped < total ? "warning" : "ok";
    },
    tooltip: "Cable geometry from KMCD Internet Infrastructure Map (693 cable systems). License: to_verify.",
  },
  {
    key: "data_centers",
    label: "PeeringDB facilities / interconnection",
    dotColor: DATA_CENTER_COLOR,
    getMapped: (c: AtlasCounts) => c.data_centers_mapped,
    getTotal: (c: AtlasCounts) => c.data_centers_total,
    getCoverage: (mapped, total) => {
      if (mapped === 0) return "disabled";
      return mapped < total ? "warning" : "ok";
    },
    tooltip: "PeeringDB public interconnection facilities, colocation sites, and data centers with coordinates. Not exhaustive of every global data center.",
  },
];

export default function LayerPanel({
  visibleLayers,
  onToggle,
  filters,
  onFilterChange,
  fuelTypes,
  countries,
  counts,
  visibleCount,
}: Props) {
  const activeFilters = [filters.fuelType, filters.country, filters.minMw > 0 ? `${filters.minMw}+ MW` : ""].filter(Boolean);

  return (
    <div className="panel-section">
      <h2>Layers</h2>
      {LAYER_CONFIG.map((cfg) => {
        const c = counts!;
        const mapped = cfg.getMapped(c);
        const total = cfg.getTotal(c);
        const coverage = cfg.getCoverage(mapped, total);
        const isDisabled = mapped === 0;
        const checked = visibleLayers[cfg.key] && !isDisabled;

        return (
          <div key={cfg.key} className="layer-row" title={cfg.tooltip}>
            <label className="layer-toggle" style={{ opacity: isDisabled ? 0.4 : 1 }}>
              <input
                type="checkbox"
                checked={checked}
                disabled={isDisabled}
                onChange={() => onToggle(cfg.key)}
              />
              <span className="layer-dot" style={{ background: cfg.dotColor }} />
              <div className="layer-info">
                <span className="layer-name">{cfg.label}</span>
                <span className="layer-counts">{mapped.toLocaleString()} / {total.toLocaleString()} mapped</span>
              </div>
              <span className={`layer-status-chip layer-status-chip--${coverage}`}>
                {coverage === "ok" ? "mapped" : coverage === "warning" ? "partial" : "unmapped"}
              </span>
            </label>
          </div>
        );
      })}

      <h2 style={{ marginTop: 14 }}>Filters</h2>
      <div className="filter-group">
        <label>Fuel Type</label>
        <select
          value={filters.fuelType}
          onChange={(e) => onFilterChange({ ...filters, fuelType: e.target.value })}
        >
          <option value="">All</option>
          {fuelTypes.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>

        <label>Country</label>
        <select
          value={filters.country}
          onChange={(e) => onFilterChange({ ...filters, country: e.target.value })}
        >
          <option value="">All</option>
          {countries.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <label>Min Capacity (MW)</label>
        <input
          type="number"
          min={0}
          step={10}
          value={filters.minMw || ""}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "" || /^\d+$/.test(v)) {
              onFilterChange({ ...filters, minMw: v === "" ? 0 : Number(v) });
            }
          }}
          placeholder="0"
        />
      </div>

      {activeFilters.length > 0 && (
        <div className="filter-summary">
          <span className="filter-summary-label">Active:</span> {activeFilters.join(", ")}
        </div>
      )}
      <div className="filter-summary">
        <span className="filter-summary-label">Visible:</span> {visibleCount.toLocaleString()} power plants
      </div>
    </div>
  );
}
