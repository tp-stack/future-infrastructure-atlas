import type { Asset } from "../map/types";

interface Props {
  asset: Asset | null;
}

export default function AssetPopup({ asset }: Props) {
  if (!asset) {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 12, color: "#52525b" }}>
          Click on the map to inspect an asset
        </div>
      </div>
    );
  }

  if ("f" in asset) {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 13, marginBottom: 4 }}>{asset.n}</div>
        <div style={{ fontSize: 11, color: "#71717a" }}>
          <div>Type: Power Plant</div>
          <div>Fuel: {asset.f}</div>
          <div>Capacity: {asset.mw.toLocaleString()} MW</div>
          <div>Country: {asset.c}</div>
        </div>
      </div>
    );
  }

  if ("op" in asset) {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 13, marginBottom: 4 }}>{asset.n}</div>
        <div style={{ fontSize: 11, color: "#71717a" }}>
          <div>Type: Data Center</div>
          <div>Owner: {asset.op || "N/A"}</div>
          <div>Country: {asset.c}</div>
          <div>Capacity: {asset.mw ? `${asset.mw.toLocaleString()} MW` : "N/A"}</div>
          <div>Precision: {asset.coordinate_precision || "N/A"}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-section">
      <h2>Selected Asset</h2>
      <div style={{ fontSize: 13, marginBottom: 4 }}>{asset.n}</div>
      <div style={{ fontSize: 11, color: "#71717a" }}>
        <div>Type: Submarine Cable</div>
        <div>Precision: {"geometry_precision" in asset ? asset.geometry_precision : "N/A"}</div>
      </div>
    </div>
  );
}
