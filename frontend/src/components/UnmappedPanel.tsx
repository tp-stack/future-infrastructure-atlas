import type { AtlasMetadata } from "../map/types";

interface Props {
  metadata: AtlasMetadata | null;
}

export default function UnmappedPanel({ metadata }: Props) {
  if (!metadata) return null;

  const c = metadata.counts;
  const cablesMapped = c.cables_mapped ?? c.submarine_cables_mapped;
  const cablesTotal = c.cables_total ?? c.submarine_cables_total;
  const cablesUnmapped = c.cables_unmapped ?? c.submarine_cables_unmapped;

  return (
    <div className="panel-section">
      <h2>Unmapped Infrastructure</h2>

      <div className="stat-row">
        <span className="stat-label">Cables loaded</span>
        <span className="stat-value">{cablesTotal.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Cables mapped</span>
        <span className="stat-value">{cablesMapped.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Cables unmapped</span>
        <span className="stat-value">{cablesUnmapped.toLocaleString()}</span>
      </div>

      <div className="stat-row" style={{ marginTop: 8 }}>
        <span className="stat-label">Data centers loaded</span>
        <span className="stat-value">{c.data_centers_total.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Data centers mapped</span>
        <span className="stat-value">{c.data_centers_mapped.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Data centers unmapped</span>
        <span className="stat-value">{c.data_centers_unmapped.toLocaleString()}</span>
      </div>

      <div className="unmapped-reason">
        <div className="unmapped-reason-item">
          <strong>Submarine cables</strong> need geometry/polyline coordinates to appear on the map.
        </div>
        <div className="unmapped-reason-item">
          <strong>Frontier AI data centers</strong> need public or licensed latitude/longitude or metro-level coordinates to appear on the map.
        </div>
      </div>

      <div className="unmapped-sources">
        <div><strong>Source:</strong> SCN Submarine Cable Network Data (github.com/miaw-net/scn-data)</div>
        <div><strong>Source:</strong> Epoch AI Frontier Data Centers (epoch.ai/data/data-centers)</div>
      </div>
    </div>
  );
}
