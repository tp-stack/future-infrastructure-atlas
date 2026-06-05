import type { PowerPlant } from "../map/types";
import { ENERGY_COLOR } from "../layers/energyFactoryLayer";

interface Props {
  plant: PowerPlant;
  showFlows: boolean;
  onToggleFlows: () => void;
  onClose: () => void;
  onFit: () => void;
}

export default function EnergyFactoryPopup({ plant, showFlows, onToggleFlows, onClose, onFit }: Props) {
  const capacityDisplay = plant.mw > 0 ? `${plant.mw.toLocaleString()} MW` : "Not available";
  const hasCapacity = plant.mw > 0;

  return (
    <div className="energy-popup">
      <div className="energy-popup-header">
        <div className="energy-popup-title">{plant.n || "Unknown power plant"}</div>
        <button className="energy-popup-close" onClick={onClose} title="Close">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="energy-popup-body">
        <div className="energy-popup-row">
          <span className="energy-popup-label">Country</span>
          <span className="energy-popup-value">{plant.c || "Unknown"}</span>
        </div>
        <div className="energy-popup-row">
          <span className="energy-popup-label">Type</span>
          <span className="energy-popup-value">{plant.f || "Unknown"}</span>
        </div>
        <div className="energy-popup-row">
          <span className="energy-popup-label">Capacity</span>
          <span className="energy-popup-value" style={{ color: hasCapacity ? "var(--accent)" : "var(--intel-missing)" }}>
            {capacityDisplay}
          </span>
        </div>
        <div className="energy-popup-row">
          <span className="energy-popup-label">Source</span>
          <span className="energy-popup-value energy-popup-source">WRI Global Power Plant Database</span>
        </div>
      </div>
      <div className="energy-popup-actions">
        <button
          className={`energy-popup-btn ${showFlows ? "active" : ""}`}
          onClick={onToggleFlows}
          disabled={!hasCapacity}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
          {showFlows ? "Hide energy flows" : "Show energy flows"}
        </button>
        <button className="energy-popup-btn energy-popup-btn--secondary" onClick={onFit}>
          Center map
        </button>
      </div>
      {showFlows && (
        <div className="energy-popup-disclaimer">
          Estimated energy flow proximity — not verified grid routing
        </div>
      )}
      <div className="energy-popup-color-bar" style={{ background: ENERGY_COLOR }} />
    </div>
  );
}
