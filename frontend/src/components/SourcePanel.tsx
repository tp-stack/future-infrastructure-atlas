import type { AtlasMetadata } from "../map/types";

interface Props {
  metadata: AtlasMetadata | null;
}

export default function SourcePanel({ metadata }: Props) {
  if (!metadata) return null;

  return (
    <div className="panel-section">
      <h2>Sources</h2>
      {metadata.sources.map((s) => (
        <div key={s.key} className="source-item">
          <a href={s.url} target="_blank" rel="noopener noreferrer">
            {s.name}
          </a>
          <div style={{ color: "#52525b" }}>{s.license}</div>
        </div>
      ))}

      <h2 style={{ marginTop: 12 }}>Disclaimer</h2>
      <div className="disclaimer-text">{metadata.disclaimer}</div>
    </div>
  );
}
