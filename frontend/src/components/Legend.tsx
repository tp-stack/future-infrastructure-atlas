import { FUEL_COLORS } from "../map/layers";

export default function Legend() {
  const fuels = Object.keys(FUEL_COLORS);
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
      <div className="layer-toggle" style={{ cursor: "default" }}>
        <span className="layer-dot" style={{ background: "#4dd0e1" }} />
        Submarine Cables
      </div>
      <div className="layer-toggle" style={{ cursor: "default" }}>
        <span className="layer-dot" style={{ background: "#e0e0e0" }} />
        Data Centers
      </div>
    </div>
  );
}
