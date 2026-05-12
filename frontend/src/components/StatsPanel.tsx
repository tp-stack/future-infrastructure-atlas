import type { AtlasMetadata } from "../map/types";
import { useMemo } from "react";

interface Props {
  metadata: AtlasMetadata | null;
  tileStatus?: { power_plants: string; submarine_cables: string; data_centers: string };
  pmtilesMode?: boolean;
}

export default function StatsPanel({ metadata, tileStatus, pmtilesMode }: Props) {
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
        { label: "PeeringDB facilities", value: c.data_centers_mapped },
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
      geometrySource: c.cable_geometry_source,
      geometryLicense: c.cable_geometry_license_status,
      geometryReview: c.cable_geometry_review_required,
      dcSource: c.data_center_source,
      dcLicense: c.data_center_license_status,
      dcReview: c.data_center_review_required,
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

      {sections.geometrySource && sections.geometrySource !== "legacy_lookup" && (
        <div className="stats-section-label" style={{ marginTop: 8 }}>Cable geometry source</div>
      )}
      {sections.geometrySource && sections.geometrySource !== "legacy_lookup" && (
        <div className="stat-row">
          <span className="stat-label">Source</span>
          <span className="stat-value">{sections.geometrySource}</span>
        </div>
      )}
      {sections.geometryLicense && sections.geometrySource !== "legacy_lookup" && (
        <div className="stat-row">
          <span className="stat-label">License</span>
          <span className="stat-value">{sections.geometryLicense}</span>
        </div>
      )}
      {sections.geometryReview && (
        <div className="license-warning" style={{ marginTop: 6, fontSize: 10, color: "#f59e0b" }}>
          Cable geometry source requires license review before production/commercial use.
        </div>
      )}

      {sections.dcSource && sections.dcSource !== "Epoch AI + manual lookup" && (
        <div className="stats-section-label" style={{ marginTop: 8 }}>Data center source</div>
      )}
      {sections.dcSource && sections.dcSource !== "Epoch AI + manual lookup" && (
        <div className="stat-row">
          <span className="stat-label">Source</span>
          <span className="stat-value">{sections.dcSource}</span>
        </div>
      )}
      {sections.dcLicense && sections.dcSource !== "Epoch AI + manual lookup" && (
        <div className="stat-row">
          <span className="stat-label">License</span>
          <span className="stat-value">{sections.dcLicense}</span>
        </div>
      )}

      {pmtilesMode && tileStatus && (
        <>
          <div className="stats-section-label" style={{ marginTop: 8 }}>Tile availability</div>
          <div className="stat-row">
            <span className="stat-label">Power plants</span>
            <span className="stat-value" style={{ color: tileStatus.power_plants === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.power_plants}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Cables</span>
            <span className="stat-value" style={{ color: tileStatus.submarine_cables === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.submarine_cables}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Data centers</span>
            <span className="stat-value" style={{ color: tileStatus.data_centers === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.data_centers}</span>
          </div>
        </>
      )}
    </div>
  );
}
