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
  const dcsMapped = c.data_centers_mapped;
  const dcsTotal = c.data_centers_total;
  const dcsUnmapped = c.data_centers_unmapped;

  return (
    <div className="panel-section">
      <h2>Data Coverage</h2>

      <div className="stat-row">
        <span className="stat-label">Cables</span>
        <span className="stat-value">{cablesMapped.toLocaleString()} / {cablesTotal.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Data centers</span>
        <span className="stat-value">{dcsMapped.toLocaleString()} / {dcsTotal.toLocaleString()}</span>
      </div>

      {(cablesUnmapped > 0 || dcsUnmapped > 0) && (
        <div className="coverage-warning" style={{ marginTop: 8, borderRadius: 4, border: '1px solid rgba(200,100,50,0.15)' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 10, marginBottom: 4, color: '#d08040' }}>Limited spatial coverage</div>
            <div className="unmapped-reason-item">
              <strong>Submarine cables:</strong> {cablesUnmapped.toLocaleString()} of {cablesTotal.toLocaleString()} records lack verified geometry and cannot be rendered on the map.
            </div>
            <div className="unmapped-reason-item">
              <strong>Data centers:</strong> {dcsUnmapped.toLocaleString()} of {dcsTotal.toLocaleString()} records lack verified coordinates and cannot be rendered.
            </div>
          </div>
        </div>
      )}

      <div className="unmapped-sources">
        <div><strong>Source:</strong> SCN Submarine Cable Network Data (github.com/miaw-net/scn-data)</div>
        <div><strong>Source:</strong> Epoch AI Frontier Data Centers (epoch.ai/data/data-centers)</div>
      </div>
    </div>
  );
}
