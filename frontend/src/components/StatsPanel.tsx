import type { AtlasMetadata } from "../map/types";
import { useMemo } from "react";

interface Props {
  metadata: AtlasMetadata | null;
}

export default function StatsPanel({ metadata }: Props) {
  const sections = useMemo(() => {
    if (!metadata) return null;

    const c = metadata.counts;
    const cablesMapped = c.cables_mapped ?? c.submarine_cables_mapped;
    const cablesTotal = c.cables_total ?? c.submarine_cables_total;
    const cablesUnmapped = c.cables_unmapped ?? c.submarine_cables_unmapped;
    const ppTotal = c.power_plants_total ?? c.power_plants_mapped + c.power_plants_rejected;

    return {
      mapped: [
        { label: "Power plants", value: c.power_plants_mapped },
        { label: "Submarine cables", value: cablesMapped },
        { label: "Data centers", value: c.data_centers_mapped },
      ],
      metadataOnly: [
        { label: "Cables (unmapped)", value: cablesUnmapped },
        { label: "Data centers (unmapped)", value: c.data_centers_unmapped },
      ],
      rejected: [
        ...(c.power_plants_rejected > 0 ? [{ label: "Power plants (rejected)", value: c.power_plants_rejected }] : []),
      ],
      totals: [
        { label: "Power plants (source)", value: ppTotal },
        { label: "Cables (source)", value: cablesTotal },
        { label: "Data centers (source)", value: c.data_centers_total },
      ],
    };
  }, [metadata]);

  if (!metadata || !sections) return null;

  return (
    <div className="panel-section">
      <h2>Statistics</h2>

      <div className="stats-section-label">Mapped infrastructure</div>
      {sections.mapped.map((s) => (
        <div key={s.label} className="stat-row">
          <span className="stat-label">{s.label}</span>
          <span className="stat-value">{s.value.toLocaleString()}</span>
        </div>
      ))}

      {sections.metadataOnly.some((s) => s.value > 0) && (
        <>
          <div className="stats-section-label">Metadata only</div>
          {sections.metadataOnly.map((s) => (
            s.value > 0 && (
              <div key={s.label} className="stat-row">
                <span className="stat-label">{s.label}</span>
                <span className="stat-value">{s.value.toLocaleString()}</span>
              </div>
            )
          ))}
        </>
      )}

      {sections.rejected.length > 0 && (
        <>
          <div className="stats-section-label">Rejected</div>
          {sections.rejected.map((s) => (
            <div key={s.label} className="stat-row">
              <span className="stat-label">{s.label}</span>
              <span className="stat-value">{s.value.toLocaleString()}</span>
            </div>
          ))}
        </>
      )}

      <div className="stats-section-label">Source totals</div>
      {sections.totals.map((s) => (
        <div key={s.label} className="stat-row">
          <span className="stat-label">{s.label}</span>
          <span className="stat-value">{s.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}
