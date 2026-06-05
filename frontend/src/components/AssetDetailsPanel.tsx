import type { Asset, PowerPlant, DataCenter, Cable, PowerLine, Substation } from "../map/types";
import { formatAssetType, type InteractableType } from "../map/interaction";
import { ENERGY_COLOR } from "../layers/energyFactoryLayer";

interface Props {
  asset: Asset | null;
  assetType?: InteractableType | null;
  onClose: () => void;
  onFitAsset?: (asset: Asset) => void;
  showEnergyFlows?: boolean;
  onToggleEnergyFlows?: (plant: PowerPlant) => void;
}

export default function AssetDetailsPanel({ asset, assetType, onClose, onFitAsset, showEnergyFlows, onToggleEnergyFlows }: Props) {
  if (!asset) return null;

  const type = assetType || asset.kind || ("f" in asset ? "power_plant" : "op" in asset ? "data_center" : "submarine_cable");
  const typeLabel = formatAssetType(type);
  const hasLicenseWarning = "source_license" in asset && (asset as unknown as Record<string, string>).source_license === "to_verify";
  const isPowerPlant = type === "power_plant" || asset.kind === "power_plant";

  return (
    <div className="asset-details-overlay" onClick={onClose}>
      <div className="asset-details-panel" onClick={(e) => e.stopPropagation()}>
        <div className="asset-details-header">
          <div className="asset-details-title">{asset.n || "Unknown"}</div>
          <button className="asset-details-close" onClick={onClose} title="Close">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <div className="asset-details-type">{typeLabel}</div>
        <div className="asset-details-body">
          {renderFields(asset, type)}
        </div>
        {onFitAsset && (type === "submarine_cable" || type === "power_plant" || type === "data_center") && (
          <button className="asset-details-fit" type="button" onClick={() => onFitAsset(asset)}>
            {type === "submarine_cable" ? "Fit cable route" : "Center on map"}
          </button>
        )}
        {onToggleEnergyFlows && isPowerPlant && (
          <button
            className={`asset-details-fit ${showEnergyFlows ? "active" : ""}`}
            type="button"
            onClick={() => onToggleEnergyFlows(asset as PowerPlant)}
            style={showEnergyFlows ? { borderColor: ENERGY_COLOR, color: ENERGY_COLOR } : undefined}
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, verticalAlign: "middle" }}>
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
            {showEnergyFlows ? "Hide energy flows" : "Show energy flows"}
          </button>
        )}
        {showEnergyFlows && isPowerPlant && (
          <div style={{ fontSize: 9, color: "#5a5a62", marginTop: 6, fontStyle: "italic", textAlign: "center" }}>
            Estimated energy flow proximity — not verified grid routing
          </div>
        )}
        {hasLicenseWarning && (
          <div className="asset-details-warning">
            Source license: to_verify — requires review before production/commercial use.
          </div>
        )}
      </div>
    </div>
  );
}

function renderConfidence(c: number): string {
  if (c >= 0.9) return "High";
  if (c >= 0.7) return "Medium";
  if (c >= 0.4) return "Low";
  return "Very low";
}

function formatLength(km: string): string {
  const n = parseFloat(km);
  if (Number.isFinite(n)) {
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k km`;
    return `${Math.round(n).toLocaleString()} km`;
  }
  return km;
}

function renderFields(asset: Asset, type: string) {
  const fields: { label: string; value: string }[] = [];

  if (type === "power_plant") {
    const pp = asset as PowerPlant;
    const hasCapacity = pp.mw != null && pp.mw > 0;
    const hasFuel = Boolean(pp.f && pp.f !== "Unknown" && pp.f !== "Other");
    const hasCoords = pp.lat != null && pp.lon != null && Math.abs(pp.lat) > 0.01 && Math.abs(pp.lon) > 0.01;
    fields.push({ label: "Fuel", value: pp.f || "Unknown" });
    fields.push({ label: "Capacity", value: hasCapacity ? `${pp.mw.toLocaleString()} MW` : "N/A" });
    fields.push({ label: "Country", value: pp.c || "Unknown" });
    fields.push({ label: "Coordinates", value: `${pp.lat?.toFixed(4)}, ${pp.lon?.toFixed(4)}` });
    return (
      <>
        <div className="asset-details-fields">
          {fields.map((f, i) => (
            <div key={i} className="asset-details-field">
              <span className="asset-details-label">{f.label}</span>
              <span className="asset-details-value">{f.value}</span>
            </div>
          ))}
        </div>
        <div className="ev-badges">
          <span className={`ev-badge ev-badge--${hasCapacity ? "observed" : "missing"}`}>
            {hasCapacity ? "[Observed]" : "[Missing]"} Capacity
          </span>
          <span className={`ev-badge ev-badge--${hasFuel ? "observed" : "proxy"}`}>
            {hasFuel ? "[Observed]" : "[Proxy]"} Fuel type
          </span>
          <span className={`ev-badge ev-badge--${hasCoords ? "observed" : "derived"}`}>
            {hasCoords ? "[Observed]" : "[Derived]"} Coordinates
          </span>
          <span className="ev-badge ev-badge--derived">[Derived] Grid proximity</span>
          <span className="ev-badge ev-badge--proxy">[Proxy] Water risk</span>
        </div>
      </>
    );
  } else if (type === "data_center") {
    const dc = asset as DataCenter;
    const hasCapacity = dc.mw != null && dc.mw > 0;
    const hasCoords = dc.lat != null && dc.lon != null && Math.abs(dc.lat) > 0.01;
    const isExact = dc.coordinate_precision && !dc.coordinate_precision.includes("metro") && dc.coordinate_precision !== "city";
    const hasNetworks = dc.net_count != null && dc.net_count > 0;
    fields.push({ label: "Owner/Operator", value: dc.op || "N/A" });
    fields.push({ label: "Country", value: dc.c || "Unknown" });
    fields.push({ label: "City", value: dc.city || "N/A" });
    fields.push({ label: "Capacity", value: hasCapacity ? `${dc.mw} MW` : "N/A" });
    fields.push({ label: "Precision", value: dc.coordinate_precision || "N/A" });
    fields.push({ label: "Source", value: dc.source || "N/A" });
    if (dc.net_count != null) fields.push({ label: "Networks", value: String(dc.net_count) });
    if (dc.ix_count != null) fields.push({ label: "IXPs", value: String(dc.ix_count) });
    fields.push({ label: "Coordinates", value: `${dc.lat?.toFixed(4)}, ${dc.lon?.toFixed(4)}` });

    return (
      <>
        <div className="asset-details-fields">
          {fields.map((f, i) => (
            <div key={i} className="asset-details-field">
              <span className="asset-details-label">{f.label}</span>
              <span className="asset-details-value">{f.value}</span>
            </div>
          ))}
        </div>
        <div className="ev-badges">
          <span className={`ev-badge ev-badge--${hasCapacity ? "observed" : "missing"}`}>
            {hasCapacity ? "[Observed]" : "[Missing]"} Capacity
          </span>
          <span className={`ev-badge ev-badge--${isExact ? "observed" : "proxy"}`}>
            {isExact ? "[Observed]" : "[Proxy]"} Location
          </span>
          <span className={`ev-badge ev-badge--${hasNetworks ? "observed" : "missing"}`}>
            {hasNetworks ? "[Observed]" : "[Missing]"} Network presence
          </span>
          <span className={`ev-badge ev-badge--${hasCoords ? "observed" : "missing"}`}>
            {hasCoords ? "[Observed]" : "[Missing]"} Coordinates
          </span>
        </div>
      </>
    );
  } else if (type === "submarine_cable") {
    const cable = asset as Cable;
    const hasOperators = Boolean(cable.operators);
    const hasLandingPoints = Boolean(cable.landing_points);
    const hasLength = Boolean(cable.length_km);
    const highConfidence = cable.confidence != null && cable.confidence >= 0.7;
    const commercial = cable.commercial_use_allowed;
    const licenseOk = cable.source_license?.includes("ODbL") || cable.source_license?.includes("CC");
    fields.push({ label: "Source", value: cable.source || "N/A" });
    fields.push({ label: "Geometry precision", value: cable.geometry_precision || "N/A" });
    if (cable.confidence != null) fields.push({ label: "Confidence", value: renderConfidence(cable.confidence) });
    fields.push({ label: "Note", value: "Generalized public geometry — not exact trench route" });

    return (
      <>
        <div className="asset-details-fields">
          {fields.map((f, i) => (
            <div key={i} className="asset-details-field">
              <span className="asset-details-label">{f.label}</span>
              <span className="asset-details-value">{f.value}</span>
            </div>
          ))}
          <div className="asset-details-field">
            <span className="asset-details-label">License</span>
            <span className={`asset-details-value license-badge license-badge--${licenseOk ? "ok" : "restricted"}`}>
              {cable.source_license || "N/A"}
            </span>
          </div>
          {cable.commercial_use_allowed !== undefined && (
            <div className="asset-details-field">
              <span className="asset-details-label">Commercial use</span>
              <span className={`asset-details-value license-badge license-badge--${commercial ? "ok" : "restricted"}`}>
                {commercial ? "Allowed" : "Requires review"}
              </span>
            </div>
          )}
          {cable.operators && (
            <div className="asset-details-field">
              <span className="asset-details-label">Operators</span>
              <span className="asset-details-value asset-details-badges">
                {cable.operators.split(",").map((op, i) => (
                  <span key={i} className="badge badge--operator">{op.trim()}</span>
                ))}
              </span>
            </div>
          )}
          {cable.length_km && (
            <div className="asset-details-field">
              <span className="asset-details-label">Length</span>
              <span className="asset-details-value">{formatLength(cable.length_km)}</span>
            </div>
          )}
          {cable.landing_points && (
            <div className="asset-details-field asset-details-field--block">
              <span className="asset-details-label">Landing points</span>
              <div className="asset-details-landing-list">
                {(Array.isArray(cable.landing_points) ? cable.landing_points : cable.landing_points.split(",").map(s => s.trim())).map((lp, i) => (
                  <span key={i} className="badge badge--landing">{lp}</span>
                ))}
              </div>
            </div>
          )}
          {cable.source_url && (
            <div className="asset-details-field">
              <span className="asset-details-label">Source URL</span>
              <span className="asset-details-value">
                <a href={cable.source_url} target="_blank" rel="noopener noreferrer" className="asset-details-link">
                  {new URL(cable.source_url).hostname}
                </a>
              </span>
            </div>
          )}
        </div>
        <div className="ev-badges">
          <span className={`ev-badge ev-badge--${highConfidence ? "observed" : "derived"}`}>
            {highConfidence ? "[Observed]" : "[Derived]"} Route geometry
          </span>
          <span className={`ev-badge ev-badge--${hasOperators ? "observed" : "missing"}`}>
            {hasOperators ? "[Observed]" : "[Missing]"} Operators
          </span>
          <span className={`ev-badge ev-badge--${hasLandingPoints ? "observed" : "missing"}`}>
            {hasLandingPoints ? "[Observed]" : "[Missing]"} Landing points
          </span>
          <span className={`ev-badge ev-badge--${hasLength ? "observed" : "missing"}`}>
            {hasLength ? "[Observed]" : "[Missing]"} Length
          </span>
          <span className={`ev-badge ev-badge--${licenseOk ? "observed" : "proxy"}`}>
            {licenseOk ? "[Observed]" : "[Proxy]"} License
          </span>
          <span className={`ev-badge ev-badge--${commercial ? "observed" : "missing"}`}>
            {commercial ? "[Observed]" : "[Missing]"} Commercial use
          </span>
        </div>
      </>
    );
  } else if (type === "power_line") {
    const line = asset as PowerLine;
    const hasVoltage = Boolean(line.voltage);
    const hasCapacity = line.s_nom_mva != null && line.s_nom_mva > 0;
    const hasLength = line.length_km != null && line.length_km > 0;
    const hasCircuits = line.circuits != null && line.circuits > 0;
    fields.push({ label: "Voltage", value: line.voltage ? `${line.voltage} kV` : "N/A" });
    fields.push({ label: "Circuits", value: line.circuits ? String(line.circuits) : "N/A" });
    fields.push({ label: "Cables", value: line.cables ? String(line.cables) : "N/A" });
    fields.push({ label: "Length", value: line.length_km ? `${line.length_km.toLocaleString()} km` : "N/A" });
    fields.push({ label: "Country", value: line.country || "N/A" });
    fields.push({ label: "Type", value: line.type || "N/A" });
    if (line.s_nom_mva != null) fields.push({ label: "Capacity", value: `${line.s_nom_mva.toLocaleString()} MVA` });
    fields.push({ label: "Underground", value: line.underground ? "Yes" : "No" });
    return (
      <>
        <div className="asset-details-fields">
          {fields.map((f, i) => (
            <div key={i} className="asset-details-field">
              <span className="asset-details-label">{f.label}</span>
              <span className="asset-details-value">{f.value}</span>
            </div>
          ))}
        </div>
        <div className="ev-badges">
          <span className={`ev-badge ev-badge--${hasVoltage ? "observed" : "missing"}`}>
            {hasVoltage ? "[Observed]" : "[Missing]"} Voltage
          </span>
          <span className={`ev-badge ev-badge--${hasCapacity ? "observed" : "missing"}`}>
            {hasCapacity ? "[Observed]" : "[Missing]"} Capacity
          </span>
          <span className={`ev-badge ev-badge--${hasLength ? "observed" : "missing"}`}>
            {hasLength ? "[Observed]" : "[Missing]"} Length
          </span>
          <span className={`ev-badge ev-badge--${hasCircuits ? "observed" : "proxy"}`}>
            {hasCircuits ? "[Observed]" : "[Proxy]"} Circuits
          </span>
          <span className="ev-badge ev-badge--derived">[Derived] Grid connectivity</span>
        </div>
      </>
    );
  } else if (type === "substation") {
    const substation = asset as Substation;
    const hasVoltage = Boolean(substation.voltage);
    const hasCoords = substation.lat != null && substation.lon != null && Math.abs(substation.lat) > 0.01;
    const hasType = Boolean(substation.symbol);
    fields.push({ label: "Voltage", value: substation.voltage ? `${substation.voltage} kV` : "N/A" });
    fields.push({ label: "Country", value: substation.country || "N/A" });
    fields.push({ label: "Type", value: substation.symbol || "N/A" });
    fields.push({ label: "DC", value: substation.dc ? "Yes" : "No" });
    fields.push({ label: "Under construction", value: substation.under_construction ? "Yes" : "No" });
    fields.push({ label: "Coordinates", value: `${substation.lat?.toFixed(4)}, ${substation.lon?.toFixed(4)}` });
    return (
      <>
        <div className="asset-details-fields">
          {fields.map((f, i) => (
            <div key={i} className="asset-details-field">
              <span className="asset-details-label">{f.label}</span>
              <span className="asset-details-value">{f.value}</span>
            </div>
          ))}
        </div>
        <div className="ev-badges">
          <span className={`ev-badge ev-badge--${hasVoltage ? "observed" : "missing"}`}>
            {hasVoltage ? "[Observed]" : "[Missing]"} Voltage
          </span>
          <span className={`ev-badge ev-badge--${hasCoords ? "observed" : "derived"}`}>
            {hasCoords ? "[Observed]" : "[Derived]"} Coordinates
          </span>
          <span className={`ev-badge ev-badge--${hasType ? "observed" : "missing"}`}>
            {hasType ? "[Observed]" : "[Missing]"} Substation type
          </span>
          <span className="ev-badge ev-badge--derived">[Derived] Grid connectivity</span>
        </div>
      </>
    );
  }

  return (
    <div className="asset-details-fields">
      {fields.map((f, i) => (
        <div key={i} className="asset-details-field">
          <span className="asset-details-label">{f.label}</span>
          <span className="asset-details-value">{f.value}</span>
        </div>
      ))}
    </div>
  );
}
