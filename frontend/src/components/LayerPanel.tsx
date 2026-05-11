import type { FilterState } from "../map/types";
import { FUEL_COLORS } from "../map/layers";

interface Props {
  visibleLayers: Record<string, boolean>;
  onToggle: (key: string) => void;
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  fuelTypes: string[];
  countries: string[];
}

export default function LayerPanel({
  visibleLayers,
  onToggle,
  filters,
  onFilterChange,
  fuelTypes,
  countries,
}: Props) {
  return (
    <div className="panel-section">
      <h2>Layers</h2>
      <label className="layer-toggle">
        <input
          type="checkbox"
          checked={visibleLayers.power_plants}
          onChange={() => onToggle("power_plants")}
        />
        <span className="layer-dot" style={{ background: "#f59e0b" }} />
        Power Plants
      </label>
      <label className="layer-toggle">
        <input
          type="checkbox"
          checked={visibleLayers.cables}
          onChange={() => onToggle("cables")}
        />
        <span className="layer-dot" style={{ background: "#4dd0e1" }} />
        Submarine Cables
      </label>
      <label className="layer-toggle">
        <input
          type="checkbox"
          checked={visibleLayers.data_centers}
          onChange={() => onToggle("data_centers")}
        />
        <span className="layer-dot" style={{ background: "#e0e0e0" }} />
        Data Centers
      </label>

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
          onChange={(e) => onFilterChange({ ...filters, minMw: Number(e.target.value) || 0 })}
          placeholder="0"
        />
      </div>
    </div>
  );
}
