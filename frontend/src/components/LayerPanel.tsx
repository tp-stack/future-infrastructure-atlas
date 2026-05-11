import type { FilterState, AtlasCounts } from "../map/types";

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
  getStatus: (c: AtlasCounts) => "mapped" | "metadata_only" | "missing_geometry" | "disabled";
  tooltip: string;
  statusLabel: string | ((c: AtlasCounts) => string);
};

const LAYER_CONFIG: LayerConfig[] = [
  {
    key: "power_plants",
    label: "Power Plants",
    dotColor: "#f59e0b",
    getMapped: (c: AtlasCounts) => c.power_plants_mapped,
    getTotal: (c: AtlasCounts) => c.power_plants_total ?? c.power_plants_mapped + c.power_plants_rejected,
    getStatus: (c: AtlasCounts) => c.power_plants_mapped > 0 ? "mapped" as const : "missing_geometry" as const,
    tooltip: "",
    statusLabel: "mapped",
  },
  {
    key: "cables",
    label: "Submarine Cables",
    dotColor: "#4dd0e1",
    getMapped: (c: AtlasCounts) => c.cables_mapped ?? c.submarine_cables_mapped,
    getTotal: (c: AtlasCounts) => c.cables_total ?? c.submarine_cables_total,
    getStatus: (c: AtlasCounts) => (c.cables_mapped ?? c.submarine_cables_mapped) > 0 ? "mapped" as const : "metadata_only" as const,
    tooltip: "Cable geometry enriched from OSM-derived lookup or landing-point interpolation.",
    statusLabel: (c: AtlasCounts) => (c.cables_mapped ?? c.submarine_cables_mapped) > 0 ? "mapped" : "metadata only",
  },
  {
    key: "data_centers",
    label: "Data Centers",
    dotColor: "#e0e0e0",
    getMapped: (c: AtlasCounts) => c.data_centers_mapped,
    getTotal: (c: AtlasCounts) => c.data_centers_total,
    getStatus: (c: AtlasCounts) => c.data_centers_mapped > 0 ? "mapped" as const : "metadata_only" as const,
    tooltip: "Coordinates enriched from curated public-disclosure lookup at metro-level precision.",
    statusLabel: (c: AtlasCounts) => c.data_centers_mapped > 0 ? "mapped" : "metadata only",
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
        const status = cfg.getStatus(c);
        const isDisabled = mapped === 0;
        const checked = visibleLayers[cfg.key] && !isDisabled;
        const statusLabel = typeof cfg.statusLabel === "function" ? cfg.statusLabel(c) : cfg.statusLabel;

        return (
          <div key={cfg.key} className="layer-row" title={cfg.tooltip}>
            <label className="layer-toggle" style={{ opacity: isDisabled ? 0.5 : 1 }}>
              <input
                type="checkbox"
                checked={checked}
                disabled={isDisabled}
                onChange={() => onToggle(cfg.key)}
              />
              <span className="layer-dot" style={{ background: cfg.dotColor }} />
              <div className="layer-info">
                <span className="layer-name">{cfg.label}</span>
                <span className="layer-counts">{mapped.toLocaleString()} / {total.toLocaleString()}</span>
              </div>
              <span className={`layer-badge layer-badge--${status}`}>{statusLabel}</span>
            </label>
            {isDisabled && <div className="layer-note">{cfg.tooltip}</div>}
          </div>
        );
      })}

      <h2 style={{ marginTop: 16 }}>Filters</h2>
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
          <span className="filter-summary-label">Active filters:</span> {activeFilters.join(", ")}
        </div>
      )}
      <div className="filter-summary">
        <span className="filter-summary-label">Visible:</span> {visibleCount.toLocaleString()} power plants
      </div>
    </div>
  );
}
