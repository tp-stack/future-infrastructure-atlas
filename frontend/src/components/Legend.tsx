import { CABLE_COLOR, DATA_CENTER_COLOR, FUEL_COLORS, POWER_CABLE_COLOR } from "../map/layers";
import type { CableCompanyStat, CableFilterState } from "../map/cables";

const FUEL_KEYS = Object.keys(FUEL_COLORS).filter((k) => k !== "Other");

interface Props {
  cableCompanyStats?: CableCompanyStat[];
  cableFilters?: CableFilterState;
}

export default function Legend({ cableCompanyStats = [], cableFilters }: Props) {
  const showCompanyLegend = Boolean(cableFilters && cableFilters.mode !== "all" && cableCompanyStats.length > 0);

  return (
    <div className="panel-section">
      <h2>Legend</h2>
      {FUEL_KEYS.map((f) => (
        <div key={f} className="layer-toggle" style={{ cursor: "default" }}>
          <span className="layer-dot" style={{ background: FUEL_COLORS[f] }} />
          {f}
        </div>
      ))}
      <div className="layer-toggle" style={{ cursor: "default", marginTop: 4 }}>
        <span className="layer-dot" style={{ background: CABLE_COLOR }} />
        Submarine Cables
      </div>
      {showCompanyLegend && (
        <div className="company-legend">
          {cableCompanyStats.slice(0, 8).map((stat) => (
            <div key={stat.operator} className="company-legend-row">
              <span className="company-legend-line" style={{ background: stat.color }} />
              <span className="company-legend-label">{stat.operator}</span>
              <span className="company-legend-count">{stat.count}</span>
            </div>
          ))}
        </div>
      )}
      <div className="layer-toggle" style={{ cursor: "default" }}>
        <span className="layer-dot layer-dot--dash" style={{ background: "transparent", color: POWER_CABLE_COLOR }} />
        Underground Power Cables
      </div>
      <div className="layer-toggle" style={{ cursor: "default" }}>
        <span className="layer-dot" style={{ background: DATA_CENTER_COLOR }} />
        Data Centers
      </div>
    </div>
  );
}
