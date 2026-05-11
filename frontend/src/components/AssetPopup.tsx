import type { PowerPlant } from "../map/types";

interface Props {
  plant: PowerPlant | null;
}

export default function AssetPopup({ plant }: Props) {
  if (!plant) {
    return (
      <div className="panel-section">
        <h2>Selected Asset</h2>
        <div style={{ fontSize: 12, color: "#52525b" }}>
          Click on the map to inspect an asset
        </div>
      </div>
    );
  }

  return (
    <div className="panel-section">
      <h2>Selected Asset</h2>
      <div style={{ fontSize: 13, marginBottom: 4 }}>{plant.n}</div>
      <div style={{ fontSize: 11, color: "#71717a" }}>
        <div>Type: Power Plant</div>
        <div>Fuel: {plant.f}</div>
        <div>Capacity: {plant.mw.toLocaleString()} MW</div>
        <div>Country: {plant.c}</div>
      </div>
    </div>
  );
}
