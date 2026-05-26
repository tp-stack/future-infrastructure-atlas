import type { CandidateSite } from "../../api/siteSelectionApi";
import SuitabilityScore from "./SuitabilityScore";
import MissingDataFlags from "./MissingDataFlags";

interface Props {
  candidate: CandidateSite;
  onSelect: (candidate: CandidateSite) => void;
}

export default function CandidateLocationCard({ candidate, onSelect }: Props) {
  const scoreColor = candidate.final_score >= 70 ? "#22c55e"
    : candidate.final_score >= 50 ? "#d69a13"
    : candidate.final_score >= 30 ? "#f59e0b"
    : "#ef4444";

  return (
    <div
      className={`ss-candidate-card ${candidate.excluded ? "ss-excluded" : ""} ${candidate.human_review_required ? "ss-review-required" : ""}`}
      onClick={() => onSelect(candidate)}
    >
      <div className="ss-candidate-header">
        <div className="ss-candidate-rank">#{candidate.rank}</div>
        <div className="ss-candidate-coords">
          {candidate.lat.toFixed(4)}, {candidate.lon.toFixed(4)}
        </div>
        <div className="ss-candidate-final-score" style={{ color: scoreColor }}>
          {candidate.final_score.toFixed(0)}
        </div>
      </div>

      <div className="ss-candidate-location">
        {candidate.country}{candidate.region !== "Unknown" ? `, ${candidate.region}` : ""}
      </div>

      <div className="ss-candidate-confidence">
        Confidence: {candidate.confidence_score.toFixed(0)}/100
      </div>

      <div className="ss-candidate-scores-compact">
        <span title="Grid">G:{candidate.grid_score.toFixed(0)}</span>
        <span title="Fiber">F:{candidate.fiber_score.toFixed(0)}</span>
        <span title="Land">L:{candidate.land_score.toFixed(0)}</span>
        <span title="Climate">C:{candidate.climate_score.toFixed(0)}</span>
        <span title="Regulatory">R:{candidate.regulatory_score.toFixed(0)}</span>
      </div>

      {candidate.nearest_substation_km !== null && (
        <div className="ss-candidate-detail">
          Substation: {candidate.nearest_substation_km.toFixed(1)} km
        </div>
      )}

      {candidate.excluded && (
        <div className="ss-exclusion-badge">Excluded</div>
      )}

      {candidate.human_review_required && (
        <div className="ss-review-badge">Review</div>
      )}

      <MissingDataFlags
        flags={candidate.missing_data_flags}
        humanReviewRequired={false}
      />
    </div>
  );
}
