import type { CandidateSite } from "../../api/siteSelectionApi";

interface Props {
  candidate: CandidateSite;
}

const SCORE_COLORS = [
  { min: 80, color: "#22c55e", label: "Strong" },
  { min: 60, color: "#d69a13", label: "Moderate" },
  { min: 40, color: "#f59e0b", label: "Marginal" },
  { min: 0, color: "#ef4444", label: "Weak" },
];

function getScoreMeta(score: number) {
  return SCORE_COLORS.find((s) => score >= s.min) || SCORE_COLORS[SCORE_COLORS.length - 1];
}

export default function ExecutiveSummary({ candidate }: Props) {
  const scoreMeta = getScoreMeta(candidate.final_score);
  const confidenceMeta = getScoreMeta(candidate.confidence_score);

  const dimensions = [
    { label: "Grid", score: candidate.grid_score },
    { label: "Fiber", score: candidate.fiber_score },
    { label: "Land", score: candidate.land_score },
    { label: "Climate", score: candidate.climate_score },
    { label: "Water", score: candidate.water_score },
    { label: "Regulatory", score: candidate.regulatory_score },
    { label: "Market", score: candidate.market_score },
  ].sort((a, b) => b.score - a.score);

  const topAdvantages = dimensions.slice(0, 3);
  const topRisks = dimensions.slice(-3).reverse();

  const missingCount = candidate.missing_data_flags?.length || 0;

  return (
    <div className="executive-summary">
      <div className="executive-summary-header">Executive Assessment</div>

      <div className="executive-summary-score-area">
        <div className="executive-summary-score" style={{ color: scoreMeta.color }}>
          {candidate.final_score.toFixed(0)}
          <span className="executive-summary-score-label">/100</span>
        </div>
        <div className="executive-summary-score-text" style={{ color: scoreMeta.color }}>
          {scoreMeta.label}
        </div>
      </div>

      <div className="executive-summary-detail">
        <div className="executive-summary-row">
          <span className="executive-summary-key">Confidence</span>
          <span className="executive-summary-val" style={{ color: confidenceMeta.color }}>
            {candidate.confidence_score.toFixed(0)}/100 — {confidenceMeta.label}
          </span>
        </div>
        <div className="executive-summary-row">
          <span className="executive-summary-key">Profile</span>
          <span className="executive-summary-val">{candidate.compute_profile}</span>
        </div>
        <div className="executive-summary-row">
          <span className="executive-summary-key">Location</span>
          <span className="executive-summary-val">
            {candidate.lat.toFixed(3)}, {candidate.lon.toFixed(3)}
          </span>
        </div>
        <div className="executive-summary-row">
          <span className="executive-summary-key">Area</span>
          <span className="executive-summary-val">{candidate.area_ha.toFixed(1)} ha</span>
        </div>
        <div className="executive-summary-row">
          <span className="executive-summary-key">Data gaps</span>
          <span className="executive-summary-val" style={{ color: missingCount > 3 ? "#ef4444" : "#f59e0b" }}>
            {missingCount} flag{missingCount !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      <div className="executive-summary-sections">
        <div className="executive-summary-section">
          <div className="executive-summary-section-title">Top Advantages</div>
          {topAdvantages.map((d) => (
            <div key={d.label} className="executive-summary-section-item executive-summary-section-item--positive">
              <span className="executive-summary-section-label">{d.label}</span>
              <span className="executive-summary-section-score">{d.score.toFixed(0)}</span>
            </div>
          ))}
        </div>

        <div className="executive-summary-section">
          <div className="executive-summary-section-title">Top Risks</div>
          {topRisks.map((d) => (
            <div key={d.label} className="executive-summary-section-item executive-summary-section-item--risk">
              <span className="executive-summary-section-label">{d.label}</span>
              <span className="executive-summary-section-score">{d.score.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </div>

      {candidate.human_review_required && (
        <div className="executive-summary-review-warning">
          Human review required — confidence is limited or critical data is missing for this profile
        </div>
      )}
    </div>
  );
}