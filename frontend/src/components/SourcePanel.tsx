import type { AtlasMetadata } from "../map/types";

interface Props {
  metadata: AtlasMetadata | null;
}

export default function SourcePanel({ metadata }: Props) {
  const needsReview = metadata?.counts?.cable_geometry_review_required;

  return (
    <div className="panel-section">
      <h2>Sources</h2>
      {metadata ? (
        <>
          {metadata.sources.map((s) => (
            <div key={s.key} className="source-item">
              <a href={s.url} target="_blank" rel="noopener noreferrer">
                {s.name}
              </a>
              <div style={{ color: "#52525b", fontSize: 10 }}>{s.license}</div>
            </div>
          ))}

          <div className="source-item" style={{ marginTop: 8, fontSize: 10, color: "#52525b" }}>
            Generated: {new Date(metadata.generated_at).toLocaleString()}
          </div>

          {needsReview && (
            <div style={{ marginTop: 8, padding: "6px 8px", background: "#2d1f00", border: "1px solid #78350f", borderRadius: 4, fontSize: 10, color: "#f59e0b" }}>
              Cable geometry source requires license review before production/commercial use.
            </div>
          )}

          <h2 style={{ marginTop: 12 }}>Disclaimer</h2>
          <div className="disclaimer-text">
            This atlas uses public or redistribution-safe data. Some infrastructure layers are metadata-only where public geometries or coordinates are unavailable. No coordinates are inferred or invented. The data center layer uses PeeringDB public facility data. It includes interconnection facilities, colocation sites, and data centers with coordinates. It is not exhaustive of every global data center.
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
