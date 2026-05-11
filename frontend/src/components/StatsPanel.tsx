import type { AtlasMetadata } from "../map/types";

interface Props {
  metadata: AtlasMetadata | null;
}

export default function StatsPanel({ metadata }: Props) {
  if (!metadata) return null;

  const c = metadata.counts;
  return (
    <div className="panel-section">
      <h2>Statistics</h2>
      <div className="stat-row">
        <span className="stat-label">Power Plants</span>
        <span className="stat-value">{c.power_plants_mapped.toLocaleString()}</span>
      </div>
      {c.power_plants_rejected > 0 && (
        <div className="stat-row">
          <span className="stat-label">Power Plants Rejected</span>
          <span className="stat-value">{c.power_plants_rejected.toLocaleString()}</span>
        </div>
      )}
      <div className="stat-row">
        <span className="stat-label">Cables (total)</span>
        <span className="stat-value">{c.submarine_cables_total.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Cables Mapped</span>
        <span className="stat-value">{c.submarine_cables_mapped.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Data Centers (total)</span>
        <span className="stat-value">{c.data_centers_total.toLocaleString()}</span>
      </div>
      {c.data_centers_unmapped > 0 && (
        <div className="stat-row">
          <span className="stat-label">Data Centers Unmapped</span>
          <span className="stat-value">{c.data_centers_unmapped.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
