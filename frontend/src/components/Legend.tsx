import { CABLE_COLOR, DATA_CENTER_COLOR, FUEL_COLORS, POWER_CABLE_COLOR } from "../map/layers";

const FUEL_KEYS = Object.keys(FUEL_COLORS).filter((k) => k !== "Other");

export default function Legend() {
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
