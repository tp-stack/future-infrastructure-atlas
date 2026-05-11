import type { AtlasMetadata } from "../map/types";

interface Props {
  metadata: AtlasMetadata | null;
}

export default function SourcePanel({ metadata }: Props) {
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

          <h2 style={{ marginTop: 12 }}>Disclaimer</h2>
          <div className="disclaimer-text">
            This atlas uses public or redistribution-safe data. Some infrastructure layers are metadata-only where public geometries or coordinates are unavailable. No coordinates are inferred or invented.
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
