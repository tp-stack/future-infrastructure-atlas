import type { CandidateSite } from "../../api/siteSelectionApi";

interface Props {
  candidate: CandidateSite;
}

function riskColor(score: number | null | undefined, inverse: boolean = false): string {
  if (score === null || score === undefined) return "var(--text-muted)";
  const val = inverse ? 100 - score : score;
  if (val >= 75) return "#ef4444";
  if (val >= 50) return "#f59e0b";
  if (val >= 25) return "#d69a13";
  return "#22c55e";
}

export default function RiskBreakdown({ candidate }: Props) {
  const items = [
    { label: "Flood risk", score: candidate.flood_risk_score, inverse: true },
    { label: "Water stress", score: candidate.water_stress_score, inverse: true },
    { label: "Regulatory stability", score: candidate.regulatory_stability_score },
  ].filter((i) => i.score !== null && i.score !== undefined);

  if (items.length === 0) return null;

  return (
    <div className="ss-risk-section">
      <h4>Risk Indicators</h4>
      {items.map((item) => (
        <div key={item.label} className="ss-risk-row">
          <span className="ss-risk-label">{item.label}</span>
          <span
            className="ss-risk-value"
            style={{ color: riskColor(item.score, item.inverse) }}
          >
            {item.score?.toFixed(0)}
          </span>
        </div>
      ))}
      {candidate.soft_constraints.length > 0 && (
        <div className="ss-soft-constraints">
          {candidate.soft_constraints.map((c, i) => (
            <div key={i} className="ss-soft-constraint">{c}</div>
          ))}
        </div>
      )}
    </div>
  );
}
