import type { AtlasCore, AtlasMetadata } from "../map/types";

interface Props {
  metadata: AtlasMetadata | null;
  core?: AtlasCore;
  tileStatus?: { power_plants: string; submarine_cables: string; data_centers: string; power_lines?: string; substations?: string };
  pmtilesMode?: boolean;
}

export default function SourcePanel({ metadata, core, tileStatus, pmtilesMode }: Props) {
  const needsReview = metadata?.counts?.cable_geometry_review_required;
  const cableGeometrySource = metadata?.counts?.cable_geometry_source;
  const cableGeometryLicense = metadata?.counts?.cable_geometry_license_status;
  const sources = [...(metadata?.sources || [])];
  const seen = new Set(sources.map((source) => source.key || source.name));
  for (const source of core?.sources || []) {
    const key = source.key || source.name;
    if (!seen.has(key)) {
      sources.push(source);
      seen.add(key);
    }
  }
  const activeLicenseWarnings = (core?.license_warnings || []).filter((warning) => warning.active);
  const activeSetupWarnings = (core?.setup_warnings || []).filter((warning) => warning.active);

  return (
    <div className="panel-section">
      <h2>Sources</h2>
      {metadata || core ? (
        <>
          {sources.map((s) => (
            <div key={s.key} className="source-item">
              <a href={s.url} target="_blank" rel="noopener noreferrer">
                {s.name}
              </a>
              <div style={{ color: "#52525b", fontSize: 10 }}>{s.license}</div>
            </div>
          ))}

          {(metadata?.generated_at || core?.generated_at) && (
            <div className="source-item" style={{ marginTop: 8, fontSize: 10, color: "#52525b" }}>
              Generated: {new Date(metadata?.generated_at || core?.generated_at || "").toLocaleString()}
            </div>
          )}

          {cableGeometrySource && (
            <div className="source-item" style={{ marginTop: 8, fontSize: 10, color: "#71717a" }}>
              <div>Cable geometry: <span style={{ color: "#a1a1aa" }}>{cableGeometrySource}</span></div>
              {cableGeometryLicense && (
                <div>License status: <span style={{ color: needsReview ? "#f59e0b" : "#a1a1aa" }}>{cableGeometryLicense}</span></div>
              )}
            </div>
          )}

          {needsReview && (
            <div style={{ marginTop: 8, padding: "6px 8px", background: "#2d1f00", border: "1px solid #78350f", borderRadius: 4, fontSize: 10, color: "#f59e0b" }}>
              Prototype cable geometry is enabled for internal use and requires license review before production/commercial use.
            </div>
          )}

          {activeLicenseWarnings.map((warning) => (
            <div key={`license-${warning.layer}`} style={{ marginTop: 8, padding: "6px 8px", background: "#2d1f00", border: "1px solid #78350f", borderRadius: 4, fontSize: 10, color: "#f59e0b" }}>
              {warning.message}
            </div>
          ))}

          {activeSetupWarnings.map((warning) => (
            <div key={`setup-${warning.layer}`} style={{ marginTop: 8, padding: "6px 8px", background: "#241f12", border: "1px solid #6f5f2a", borderRadius: 4, fontSize: 10, color: "#f4d03f" }}>
              {warning.message}
            </div>
          ))}

          {pmtilesMode && tileStatus && (
            <>
              <h2 style={{ marginTop: 12 }}>Architecture</h2>
              <div className="source-item" style={{ fontSize: 10, color: "#52525b" }}>
                <div>Mode: <span style={{ color: "#4cc9e8" }}>PMTiles + canvas fallback</span></div>
                <div>Power plants: <span style={{ color: tileStatus.power_plants === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.power_plants}</span></div>
                <div>Cables: <span style={{ color: tileStatus.submarine_cables === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.submarine_cables}</span></div>
                <div>Data centers: <span style={{ color: tileStatus.data_centers === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.data_centers}</span></div>
                {tileStatus.power_lines && <div>Power lines: <span style={{ color: tileStatus.power_lines === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.power_lines}</span></div>}
                {tileStatus.substations && <div>Substations: <span style={{ color: tileStatus.substations === "present" ? "#62c370" : "#d95c5c" }}>{tileStatus.substations}</span></div>}
                <div style={{ marginTop: 4, color: "#71717a" }}>Heavy layers served via PMTiles vector tiles. Fallback canvas renderer uses atlas_web_data.json.</div>
              </div>
            </>
          )}

          <h2 style={{ marginTop: 12 }}>Disclaimer</h2>
          <div className="disclaimer-text">
            {core?.disclaimer || metadata?.disclaimer || "This atlas uses public or redistribution-safe data. Some infrastructure layers are metadata-only where public geometries or coordinates are unavailable. No coordinates are inferred or invented."}
          </div>
        </>
      ) : (
        <div className="disclaimer-text" style={{ color: "#52525b" }}>
          Source data not available. The atlas requires atlas_web_data.json to be present in the public data directory.
        </div>
      )}
    </div>
  );
}
