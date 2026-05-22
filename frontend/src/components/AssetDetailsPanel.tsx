import type { Asset, PowerPlant, DataCenter, Cable, PowerLine, Substation } from "../map/types";
import { formatAssetType, type InteractableType } from "../map/interaction";

interface Props {
  asset: Asset | null;
  assetType?: InteractableType | null;
  onClose: () => void;
}

export default function AssetDetailsPanel({ asset, assetType, onClose }: Props) {
  if (!asset) return null;

  const type = assetType || asset.kind || ("f" in asset ? "power_plant" : "op" in asset ? "data_center" : "submarine_cable");
  const typeLabel = formatAssetType(type);
  const hasLicenseWarning = "source_license" in asset && (asset as unknown as Record<string, string>).source_license === "to_verify";

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
    fields.push({ label: "Fuel", value: pp.f || "Unknown" });
    fields.push({ label: "Capacity", value: pp.mw != null ? `${pp.mw.toLocaleString()} MW` : "N/A" });
    fields.push({ label: "Country", value: pp.c || "Unknown" });
    fields.push({ label: "Coordinates", value: `${pp.lat?.toFixed(4)}, ${pp.lon?.toFixed(4)}` });
  } else if (type === "data_center") {
    const dc = asset as DataCenter;
    fields.push({ label: "Owner/Operator", value: dc.op || "N/A" });
    fields.push({ label: "Country", value: dc.c || "Unknown" });
    fields.push({ label: "City", value: dc.city || "N/A" });
    fields.push({ label: "Capacity", value: dc.mw != null ? `${dc.mw} MW` : "N/A" });
    fields.push({ label: "Precision", value: dc.coordinate_precision || "N/A" });
    fields.push({ label: "Source", value: dc.source || "N/A" });
    if (dc.net_count != null) fields.push({ label: "Networks", value: String(dc.net_count) });
    if (dc.ix_count != null) fields.push({ label: "IXPs", value: String(dc.ix_count) });
    fields.push({ label: "Coordinates", value: `${dc.lat?.toFixed(4)}, ${dc.lon?.toFixed(4)}` });

    if (dc.coordinate_precision?.includes("metro") || dc.coordinate_precision === "city") {
      fields.push({ label: "Note", value: "Metro-level coordinates — not exact facility location" });
    }
  } else if (type === "submarine_cable") {
    const cable = asset as Cable;
    fields.push({ label: "Source", value: cable.source || "N/A" });
    fields.push({ label: "Geometry precision", value: cable.geometry_precision || "N/A" });
    fields.push({ label: "License", value: cable.source_license || "N/A" });
    if (cable.confidence != null) fields.push({ label: "Confidence", value: renderConfidence(cable.confidence) });
    fields.push({ label: "Note", value: "Generalized public geometry — not exact trench route" });

    return (
      <div className="asset-details-fields">
        {fields.map((f, i) => (
          <div key={i} className="asset-details-field">
            <span className="asset-details-label">{f.label}</span>
            <span className="asset-details-value">{f.value}</span>
          </div>
        ))}
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
              {cable.landing_points.split(",").map((lp, i) => (
                <span key={i} className="badge badge--landing">{lp.trim()}</span>
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
    );
  } else if (type === "power_line") {
    const line = asset as PowerLine;
    fields.push({ label: "Voltage", value: line.voltage ? `${line.voltage} kV` : "N/A" });
    fields.push({ label: "Circuits", value: line.circuits ? String(line.circuits) : "N/A" });
    fields.push({ label: "Cables", value: line.cables ? String(line.cables) : "N/A" });
    fields.push({ label: "Length", value: line.length_km ? `${line.length_km.toLocaleString()} km` : "N/A" });
    fields.push({ label: "Country", value: line.country || "N/A" });
    fields.push({ label: "Type", value: line.type || "N/A" });
    if (line.s_nom_mva != null) fields.push({ label: "Capacity", value: `${line.s_nom_mva.toLocaleString()} MVA` });
    fields.push({ label: "Underground", value: line.underground ? "Yes" : "No" });
  } else if (type === "substation") {
    const substation = asset as Substation;
    fields.push({ label: "Voltage", value: substation.voltage ? `${substation.voltage} kV` : "N/A" });
    fields.push({ label: "Country", value: substation.country || "N/A" });
    fields.push({ label: "Type", value: substation.symbol || "N/A" });
    fields.push({ label: "DC", value: substation.dc ? "Yes" : "No" });
    fields.push({ label: "Under construction", value: substation.under_construction ? "Yes" : "No" });
    fields.push({ label: "Coordinates", value: `${substation.lat?.toFixed(4)}, ${substation.lon?.toFixed(4)}` });
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
