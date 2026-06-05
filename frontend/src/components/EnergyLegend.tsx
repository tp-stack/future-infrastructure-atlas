import { ENERGY_COLOR, ENERGY_UNKNOWN_COLOR } from "../layers/energyFactoryLayer";

export default function EnergyLegend() {
  const sizes = [
    { label: "Small energy factory", radius: 4, mw: "< 50 MW" },
    { label: "Medium energy factory", radius: 7, mw: "50–500 MW" },
    { label: "Large energy factory", radius: 12, mw: "500+ MW" },
    { label: "Unknown capacity", radius: 4, mw: "No data", color: ENERGY_UNKNOWN_COLOR },
  ];

  return (
    <div className="panel-section energy-legend">
      <h2>Energy Factory Scale</h2>
      <div className="energy-legend-items">
        {sizes.map((s, i) => (
          <div key={i} className="energy-legend-item">
            <div className="energy-legend-marker-wrap">
              <div
                className="energy-legend-marker"
                style={{
                  width: s.radius * 2,
                  height: s.radius * 2,
                  background: s.color || ENERGY_COLOR,
                  opacity: s.color ? 0.4 : 0.25,
                  borderColor: s.color ? s.color : ENERGY_COLOR,
                }}
              />
            </div>
            <div className="energy-legend-info">
              <span className="energy-legend-label">{s.label}</span>
              <span className="energy-legend-mw">{s.mw}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="energy-legend-flow">
        <div className="energy-legend-flow-line" />
        <span className="energy-legend-flow-label">Estimated energy flow proximity</span>
      </div>
    </div>
  );
}
