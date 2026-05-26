import type { CandidateSite } from "../../api/siteSelectionApi";
import MissingDataFlags from "./MissingDataFlags";

interface Props {
  candidate: CandidateSite;
  onSelect: (candidate: CandidateSite) => void;
}

const EVIDENCE_DOT_COLORS: Record<string, string> = {
  observed: "#22c55e",
  derived: "#d69a13",
  proxy: "#f59e0b",
  missing: "#ef4444",
};

function evidenceDot(quality: string | null): string {
  return EVIDENCE_DOT_COLORS[quality || ""] || "#6a6a72";
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
        <span title="Grid" style={{ color: evidenceDot(candidate.grid_evidence_quality) }}>
          G:{candidate.grid_score.toFixed(0)}
        </span>
        <span title="Fiber" style={{ color: evidenceDot(candidate.fiber_evidence_quality) }}>
          F:{candidate.fiber_score.toFixed(0)}
        </span>
        <span title="Land" style={{ color: evidenceDot(candidate.land_evidence_quality) }}>
          L:{candidate.land_score.toFixed(0)}
        </span>
        <span title="Climate" style={{ color: evidenceDot(candidate.climate_evidence_quality) }}>
          C:{candidate.climate_score.toFixed(0)}
        </span>
        <span title="Regulatory" style={{ color: evidenceDot(candidate.regulatory_evidence_quality) }}>
          R:{candidate.regulatory_score.toFixed(0)}
        </span>
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
