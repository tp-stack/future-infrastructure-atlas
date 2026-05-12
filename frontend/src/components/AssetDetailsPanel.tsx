import type { Asset, PowerPlant, DataCenter, Cable } from "../map/types";
import { formatAssetType, type InteractableType } from "../map/interaction";

interface Props {
  asset: Asset | null;
  assetType?: InteractableType | null;
  onClose: () => void;
}

export default function AssetDetailsPanel({ asset, assetType, onClose }: Props) {
  if (!asset) return null;

  const type = assetType || ("f" in asset ? "power_plant" : "op" in asset ? "data_center" : "submarine_cable");
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
    if (cable.operators) fields.push({ label: "Operators", value: cable.operators });
    if (cable.length_km) fields.push({ label: "Length", value: cable.length_km });
    if (cable.landing_points) fields.push({ label: "Landing points", value: cable.landing_points.substring(0, 200) });
    if (cable.confidence != null) fields.push({ label: "Confidence", value: String(cable.confidence) });
    fields.push({ label: "Note", value: "Generalized public geometry — not exact trench route" });
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
