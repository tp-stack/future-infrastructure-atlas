import type { Asset } from "../map/types";

interface Props {
  asset: Asset | null;
}

export default function AssetPopup({ asset }: Props) {
  if (!asset) {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 11, color: "#5a5a62" }}>
          Click on the map to inspect an asset
        </div>
      </div>
    );
  }

  if (asset.kind === "power_plant") {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 12, marginBottom: 4, color: "#f4efe6", fontWeight: 600 }}>{asset.n}</div>
        <div style={{ fontSize: 10, color: "#6a6a72", lineHeight: 1.6 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Type</span><span style={{ color: "#f4efe6" }}>Power Plant</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Fuel</span><span style={{ color: "#f4efe6" }}>{asset.f}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Capacity</span><span style={{ color: "#f4efe6" }}>{asset.mw.toLocaleString()} MW</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Country</span><span style={{ color: "#f4efe6" }}>{asset.c}</span></div>
        </div>
      </div>
    );
  }

  if (asset.kind === "data_center") {
    const isMetroLevel = asset.coordinate_precision?.includes("metro") || asset.coordinate_precision === "city";
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 12, marginBottom: 4, color: "#f4efe6", fontWeight: 600 }}>{asset.n}</div>
        <div style={{ fontSize: 10, color: "#6a6a72", lineHeight: 1.6 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Type</span><span style={{ color: "#f4efe6" }}>Data Center</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Owner</span><span style={{ color: "#f4efe6" }}>{asset.op || "N/A"}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Country</span><span style={{ color: "#f4efe6" }}>{asset.c}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Capacity</span><span style={{ color: "#f4efe6" }}>{asset.mw ? `${asset.mw.toLocaleString()} MW` : "N/A"}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Precision</span><span style={{ color: "#f4efe6" }}>{asset.coordinate_precision || "N/A"}</span></div>
        </div>
        {isMetroLevel && (
          <div style={{ fontSize: 9, color: "#5a5a62", marginTop: 6, fontStyle: "italic" }}>Metro-level coordinates — not exact facility location</div>
        )}
      </div>
    );
  }

  if (asset.kind === "power_line") {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 12, marginBottom: 4, color: "#f4efe6", fontWeight: 600 }}>{asset.n}</div>
        <div style={{ fontSize: 10, color: "#6a6a72", lineHeight: 1.6 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Type</span><span style={{ color: "#f4efe6" }}>Power Line</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Voltage</span><span style={{ color: "#f4efe6" }}>{asset.voltage || "N/A"} kV</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Circuits</span><span style={{ color: "#f4efe6" }}>{asset.circuits || "N/A"}</span></div>
          {asset.cables ? <div style={{ display: "flex", justifyContent: "space-between" }}><span>Cables</span><span style={{ color: "#f4efe6" }}>{asset.cables}</span></div> : null}
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Length</span><span style={{ color: "#f4efe6" }}>{asset.length_km ? `${asset.length_km.toLocaleString()} km` : "N/A"}</span></div>
        </div>
      </div>
    );
  }

  if (asset.kind === "substation") {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 12, marginBottom: 4, color: "#f4efe6", fontWeight: 600 }}>{asset.n}</div>
        <div style={{ fontSize: 10, color: "#6a6a72", lineHeight: 1.6 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Type</span><span style={{ color: "#f4efe6" }}>Substation</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Voltage</span><span style={{ color: "#f4efe6" }}>{asset.voltage || "N/A"} kV</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Country</span><span style={{ color: "#f4efe6" }}>{asset.country || "N/A"}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>DC</span><span style={{ color: "#f4efe6" }}>{asset.dc ? "Yes" : "No"}</span></div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-section">
      <h2>Selected Asset</h2>
      <div style={{ fontSize: 12, marginBottom: 4, color: "#f4efe6", fontWeight: 600 }}>{asset.n}</div>
      <div style={{ fontSize: 10, color: "#6a6a72", lineHeight: 1.6 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}><span>Type</span><span style={{ color: "#f4efe6" }}>Submarine Cable</span></div>
        <div style={{ display: "flex", justifyContent: "space-between" }}><span>Precision</span><span style={{ color: "#f4efe6" }}>{"geometry_precision" in asset ? asset.geometry_precision : "N/A"}</span></div>
      </div>
      <div style={{ fontSize: 9, color: "#5a5a62", marginTop: 6, fontStyle: "italic" }}>Generalized public geometry — not exact trench route</div>
    </div>
  );
}
