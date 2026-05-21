import { useMemo } from "react";
import type { AtlasData, FilterState } from "../map/types";
import { FUEL_COLORS } from "../map/layers";

interface Props {
  data: AtlasData;
  filters: FilterState;
}

const OTHER_COLOR = "#8d93a1";

export default function StatsDashboard({ data, filters }: Props) {
  const fuelData = useMemo(() => {
    const counts: Record<string, number> = {};
    let total = 0;
    for (const p of data.power_plants) {
      if (filters.fuelType && p.f !== filters.fuelType) continue;
      if (filters.country && p.c !== filters.country) continue;
      if (filters.minMw > 0 && p.mw < filters.minMw) continue;
      const fuel = p.f || "Other";
      counts[fuel] = (counts[fuel] || 0) + 1;
      total++;
    }
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return { entries, total };
  }, [data, filters]);

  const capacityByCountry = useMemo(() => {
    const map: Record<string, number> = {};
    for (const p of data.power_plants) {
      if (filters.fuelType && p.f !== filters.fuelType) continue;
      if (filters.country && p.c !== filters.country) continue;
      if (filters.minMw > 0 && p.mw < filters.minMw) continue;
      if (p.mw > 0) map[p.c] = (map[p.c] || 0) + p.mw;
    }
    return Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 10);
  }, [data, filters]);

  const countByCountry = useMemo(() => {
    const map: Record<string, number> = {};
    for (const p of data.power_plants) {
      if (filters.fuelType && p.f !== filters.fuelType) continue;
      if (filters.country && p.c !== filters.country) continue;
      if (filters.minMw > 0 && p.mw < filters.minMw) continue;
      map[p.c] = (map[p.c] || 0) + 1;
    }
    return Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 10);
  }, [data, filters]);

  const dcStats = useMemo(() => {
    let mapped = 0;
    let total = 0;
    for (const d of data.data_centers) {
      total++;
      if (d.mapped_status === "mapped") mapped++;
    }
    return { mapped, total };
  }, [data]);

  const cableStats = useMemo(() => {
    let mapped = 0;
    let total = 0;
    for (const c of data.cables) {
      total++;
      if (c.mapped_status === "mapped") mapped++;
    }
    return { mapped, total };
  }, [data]);

  const fuelColors = FUEL_COLORS as Record<string, string>;

  return (
    <div className="panel-section">
      <h2>Statistics</h2>

      <div className="stats-summary">
        <div className="stats-summary-row">
          <span className="stats-summary-label">Power plants</span>
          <span className="stats-summary-value">{fuelData.total.toLocaleString()}</span>
        </div>
        <div className="stats-summary-row">
          <span className="stats-summary-label">Data centers</span>
          <span className="stats-summary-value">{dcStats.mapped.toLocaleString()} / {dcStats.total.toLocaleString()}</span>
        </div>
        <div className="stats-summary-row">
          <span className="stats-summary-label">Cables</span>
          <span className="stats-summary-value">{cableStats.mapped.toLocaleString()} / {cableStats.total.toLocaleString()}</span>
        </div>
      </div>

      <h3 className="stats-chart-title">Fuel mix</h3>
      {fuelData.entries.length > 0 && (
        <div className="stats-donut-container">
          <svg viewBox="0 0 120 120" className="stats-donut">
            {buildDonutSegments(fuelData.entries, fuelColors)}
          </svg>
          <div className="stats-donut-center">
            <span className="stats-donut-count">{fuelData.total.toLocaleString()}</span>
            <span className="stats-donut-label">plants</span>
          </div>
        </div>
      )}
      <div className="stats-legend">
        {fuelData.entries.slice(0, 8).map(([fuel, count]) => (
          <div key={fuel} className="stats-legend-row">
            <span className="stats-legend-dot" style={{ background: fuelColors[fuel] || OTHER_COLOR }} />
            <span className="stats-legend-label">{fuel}</span>
            <span className="stats-legend-count">{count.toLocaleString()}</span>
          </div>
        ))}
        {fuelData.entries.length > 8 && (
          <div className="stats-legend-row stats-legend-more">
            +{fuelData.entries.length - 8} more fuel types
          </div>
        )}
      </div>

      <h3 className="stats-chart-title">Top 10 countries by capacity</h3>
      {capacityByCountry.length > 0 && (
        <div className="stats-bar-container">
          {buildBarChart(capacityByCountry, "GW")}
        </div>
      )}

      <h3 className="stats-chart-title">Top 10 countries by plant count</h3>
      {countByCountry.length > 0 && (
        <div className="stats-bar-container">
          {buildBarChart(countByCountry, "")}
        </div>
      )}
    </div>
  );
}

function buildDonutSegments(entries: [string, number][], colors: Record<string, string>): React.ReactNode[] {
  const total = entries.reduce((s, [, c]) => s + c, 0);
  if (total === 0) return [];
  const cx = 60, cy = 60, r = 46, sw = 10;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  return entries.map(([fuel, count]) => {
    const pct = count / total;
    const len = circ * pct;
    const dash = `${len} ${circ - len}`;
    const el = (
      <circle
        key={fuel}
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke={colors[fuel] || OTHER_COLOR}
        strokeWidth={sw}
        strokeDasharray={dash}
        strokeDashoffset={-offset}
        transform={`rotate(-90 ${cx} ${cy})`}
        className="stats-donut-segment"
      />
    );
    offset += len;
    return el;
  });
}

function buildBarChart(data: [string, number][], unit: string): React.ReactNode {
  const maxVal = Math.max(...data.map(([, v]) => v), 1);
  return (
    <div className="stats-bars">
      {data.map(([label, value]) => (
        <div key={label} className="stats-bar-row">
          <span className="stats-bar-label" title={label}>{label}</span>
          <div className="stats-bar-track">
            <div
              className="stats-bar-fill"
              style={{ width: `${(value / maxVal) * 100}%` }}
            />
          </div>
          <span className="stats-bar-value">
            {unit === "GW" ? `${(value / 1000).toFixed(1)}` : value.toLocaleString()}{unit && ` ${unit}`}
          </span>
        </div>
      ))}
    </div>
  );
}
