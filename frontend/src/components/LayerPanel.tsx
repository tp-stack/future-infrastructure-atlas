import type { FilterState, AtlasCounts, Asset } from "../map/types";
import type { CableCompanyStat, CableFilterState, CableViewMode } from "../map/cables";
import { CABLE_COLOR, DATA_CENTER_COLOR, POWER_CABLE_COLOR, POWER_LINE_COLORS, SUBSTATION_COLOR } from "../map/layers";
import { GRID_CONTINENTS, type GridContinentFilters, type GridContinentKey } from "../map/continents";

interface Props {
  visibleLayers: Record<string, boolean>;
  onToggle: (key: string) => void;
  onSetAllLayers?: (visible: boolean) => void;
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  fuelTypes: string[];
  countries: string[];
  counts: AtlasCounts | null;
  visibleCount: number;
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
  searchResults?: Array<{ label: string; type: string; asset: Asset }>;
  onSearchResultClick?: (asset: Asset) => void;
  layerOpacity?: Record<string, number>;
  onOpacityChange?: (key: string, value: number) => void;
  cableCompanyStats?: CableCompanyStat[];
  cableFilters?: CableFilterState;
  onCableFiltersChange?: (filters: CableFilterState) => void;
  onFitCables?: () => void;
  showGridContinentControls?: boolean;
  gridContinentFilters?: GridContinentFilters;
  onGridContinentToggle?: (key: GridContinentKey) => void;
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
  {
    key: "power_lines",
    label: "Power Lines",
    dotColor: POWER_LINE_COLORS[400] || "#e06000",
    getMapped: (c: AtlasCounts) => c.power_lines_mapped ?? 1,
    getTotal: (c: AtlasCounts) => c.power_lines_total ?? c.power_lines_mapped ?? 1,
    getCoverage: () => "ok",
    tooltip: `OSM power lines from OpenStreetMap. Underground and power=cable geometries render as dashed ${POWER_CABLE_COLOR} lines when present in the tile (ODbL 1.0).`,
  },
  {
    key: "substations",
    label: "Substations",
    dotColor: SUBSTATION_COLOR,
    getMapped: (c: AtlasCounts) => c.substations_mapped ?? 1,
    getTotal: (c: AtlasCounts) => c.substations_total ?? c.substations_mapped ?? 1,
    getCoverage: () => "ok",
    tooltip: "Electric substations from OSM/PyPSA-compatible source data (ODbL 1.0)",
  },
];

export default function LayerPanel({
  visibleLayers,
  layerOpacity,
  onOpacityChange,
  onToggle,
  onSetAllLayers,
  filters,
  onFilterChange,
  fuelTypes,
  countries,
  counts,
  visibleCount,
  searchQuery = "",
  onSearchChange,
  searchResults,
  onSearchResultClick,
  cableCompanyStats = [],
  cableFilters,
  onCableFiltersChange,
  onFitCables,
  showGridContinentControls = false,
  gridContinentFilters,
  onGridContinentToggle,
}: Props) {
  const activeFilters = [filters.fuelType, filters.country, filters.minMw > 0 ? `${filters.minMw}+ MW` : ""].filter(Boolean);
  const activeCableCompany = cableCompanyStats.find((stat) => stat.operator === cableFilters?.operator);

  const setCableMode = (mode: CableViewMode) => {
    if (!cableFilters || !onCableFiltersChange) return;
    onCableFiltersChange({ ...cableFilters, mode });
  };

  const setCableOperator = (operator: string) => {
    if (!cableFilters || !onCableFiltersChange) return;
    const isActive = cableFilters.operator === operator;
    onCableFiltersChange({
      ...cableFilters,
      operator: isActive ? "" : operator,
      mode: isActive ? "all" : "company",
    });
  };

  return (
    <div className="panel-section">
      <div className="layer-section-header">
        <h2>Layers</h2>
        {onSetAllLayers && (
          <div className="layer-bulk-actions" aria-label="Bulk layer controls">
            <button type="button" onClick={() => onSetAllLayers(true)}>
              All On
            </button>
            <button type="button" onClick={() => onSetAllLayers(false)}>
              All Off
            </button>
          </div>
        )}
      </div>
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
            {onOpacityChange && layerOpacity && cfg.key in layerOpacity && (
              <div className="layer-opacity-row">
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={layerOpacity[cfg.key]}
                  onChange={(e) => onOpacityChange(cfg.key, Number(e.target.value))}
                  className="layer-opacity-slider"
                />
                <span className="layer-opacity-val">{Math.round(layerOpacity[cfg.key] * 100)}%</span>
              </div>
            )}
          </div>
        );
      })}

      {showGridContinentControls && gridContinentFilters && onGridContinentToggle && (
        <div className={`grid-continent-control ${visibleLayers.power_lines ? "" : "disabled"}`}>
          <div className="grid-continent-header">
            <h2>Electric Grid Continents</h2>
            <span>{GRID_CONTINENTS.filter((continent) => gridContinentFilters[continent.key]).length} / {GRID_CONTINENTS.length} on</span>
          </div>
          <div className="grid-continent-switches" aria-label="Electric grid continent switches">
            {GRID_CONTINENTS.map((continent) => (
              <button
                key={continent.key}
                type="button"
                className={gridContinentFilters[continent.key] ? "active" : ""}
                onClick={() => onGridContinentToggle(continent.key)}
                aria-pressed={gridContinentFilters[continent.key]}
                title={`${gridContinentFilters[continent.key] ? "Hide" : "Show"} electric grid in ${continent.label}`}
              >
                {continent.shortLabel}
              </button>
            ))}
          </div>
        </div>
      )}

      {cableFilters && onCableFiltersChange && (
        <div className="cable-focus">
          <div className="cable-focus-header">
            <div>
              <h2>Cable Companies</h2>
              <div className="cable-focus-subtitle">
                {activeCableCompany
                  ? `${activeCableCompany.count.toLocaleString()} mapped cable${activeCableCompany.count === 1 ? "" : "s"}`
                  : "Color and focus cables by operator"}
              </div>
            </div>
            <button type="button" className="cable-action-btn" onClick={onFitCables} disabled={!onFitCables}>
              Fit
            </button>
          </div>

          <div className="segmented-control" aria-label="Cable view mode">
            {(["all", "company", "selected"] as CableViewMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                className={cableFilters.mode === mode ? "active" : ""}
                onClick={() => setCableMode(mode)}
              >
                {mode === "all" ? "All" : mode === "company" ? "Company" : "Selected"}
              </button>
            ))}
          </div>

          <div className="cable-company-list">
            {cableCompanyStats.map((stat) => (
              <button
                key={stat.operator}
                type="button"
                className={`cable-company-chip ${cableFilters.operator === stat.operator ? "active" : ""}`}
                onClick={() => setCableOperator(stat.operator)}
                title={`${stat.operator}: ${stat.count.toLocaleString()} mapped cables`}
              >
                <span className="cable-company-swatch" style={{ background: stat.color }} />
                <span className="cable-company-name">{stat.operator}</span>
                <span className="cable-company-count">{stat.count.toLocaleString()}</span>
              </button>
            ))}
          </div>

          {(cableFilters.operator || cableFilters.selectedCableName) && (
            <button
              type="button"
              className="cable-clear-btn"
              onClick={() => onCableFiltersChange({ operator: "", mode: "all", selectedCableName: "" })}
            >
              Clear cable focus
            </button>
          )}
        </div>
      )}

      {onSearchChange && (
        <>
          <h2 style={{ marginTop: 14 }}>Search</h2>
          <div className="filter-group">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Name, company, landing point..."
              className="search-input"
            />
          </div>
          {searchQuery && searchResults && searchResults.length > 0 && (
            <div className="search-results">
              {searchResults.slice(0, 15).map((r, i) => (
                <div
                  key={i}
                  className="search-result-item"
                  onClick={() => onSearchResultClick?.(r.asset)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter") onSearchResultClick?.(r.asset); }}
                >
                  <span className={`search-result-dot search-result-dot--${r.type}`} />
                  <span className="search-result-label">{r.label}</span>
                </div>
              ))}
              {searchResults.length > 15 && (
                <div className="search-result-more">+{searchResults.length - 15} more</div>
              )}
            </div>
          )}
          {searchQuery && searchResults && searchResults.length === 0 && (
            <div className="filter-summary">
              <span className="filter-summary-label">No results for "{searchQuery}"</span>
            </div>
          )}
        </>
      )}

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
