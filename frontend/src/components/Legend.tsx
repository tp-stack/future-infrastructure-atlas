import { FUEL_COLORS } from "../map/layers";

export default function Legend() {
  return (
    <div className="panel-section">
      <h2>Legend</h2>
      {["Hydro", "Solar", "Wind", "Natural Gas", "Nuclear", "Coal", "Oil", "Other"].map(
        (f) => (
          <div key={f} className="layer-toggle" style={{ cursor: "default" }}>
            <span className="layer-dot" style={{ background: FUEL_COLORS[f] }} />
            {f}
          </div>
        )
      )}
      <div className="layer-toggle" style={{ cursor: "default", marginTop: 4 }}>
        <span className="layer-dot" style={{ background: "#4cc9e8" }} />
        Submarine Cables
      </div>
      <div className="layer-toggle" style={{ cursor: "default" }}>
        <span className="layer-dot" style={{ background: "#e8e5dc" }} />
        Data Centers
      </div>
    </div>
  );
}
