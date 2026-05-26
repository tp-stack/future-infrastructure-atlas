import { useMemo } from "react";

interface Props {
  label: string;
  score: number;
  confidence?: number;
  size?: "small" | "large";
}

function scoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#d69a13";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

export default function SuitabilityScore({ label, score, confidence, size = "small" }: Props) {
  const barWidth = useMemo(() => `${Math.max(0, Math.min(100, score))}%`, [score]);
  const color = useMemo(() => scoreColor(score), [score]);

  return (
    <div className="ss-score-row">
      <div className="ss-score-header">
        <span className={`ss-score-label ${size}`}>{label}</span>
        <span className={`ss-score-value ${size}`} style={{ color }}>
          {score.toFixed(0)}
        </span>
      </div>
      <div className="ss-score-bar-track">
        <div
          className="ss-score-bar-fill"
          style={{ width: barWidth, background: color }}
        />
      </div>
      {confidence !== undefined && (
        <div className="ss-confidence-row">
          <span className="ss-confidence-label">Confidence</span>
          <span className="ss-confidence-value">{confidence.toFixed(0)}</span>
        </div>
      )}
    </div>
  );
}
