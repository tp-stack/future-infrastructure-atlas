import { useState } from "react";
import type { CandidateSite } from "../../api/siteSelectionApi";
import SuitabilityScore from "./SuitabilityScore";
import RiskBreakdown from "./RiskBreakdown";
import MissingDataFlags from "./MissingDataFlags";

interface Props {
  candidate: CandidateSite;
  onClose: () => void;
}

export default function EvidenceDrawer({ candidate, onClose }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="ss-evidence-drawer">
      <div className="ss-evidence-header">
        <h3>Candidate #{candidate.rank}</h3>
        <button className="ss-evidence-close" onClick={onClose}>x</button>
      </div>

      <div className="ss-evidence-location">
        {candidate.lat.toFixed(4)}, {candidate.lon.toFixed(4)}
        <span className="ss-evidence-location-detail">
          {" "}— {candidate.country}, {candidate.region}
        </span>
      </div>

      <div className="ss-evidence-scores">
        <SuitabilityScore label="Grid" score={candidate.grid_score} size="small" />
        <SuitabilityScore label="Fiber" score={candidate.fiber_score} size="small" />
        <SuitabilityScore label="Land" score={candidate.land_score} size="small" />
        <SuitabilityScore label="Climate" score={candidate.climate_score} size="small" />
        <SuitabilityScore label="Water" score={candidate.water_score} size="small" />
        <SuitabilityScore label="Regulatory" score={candidate.regulatory_score} size="small" />
        <SuitabilityScore label="Market" score={candidate.market_score} size="small" />
      </div>

      <RiskBreakdown candidate={candidate} />
      <MissingDataFlags flags={candidate.missing_data_flags} humanReviewRequired={candidate.human_review_required} />

      <div className="ss-evidence-summary">
        <button
          className="ss-evidence-toggle"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Hide" : "Show"} evidence
        </button>
        {expanded && (
          <p className="ss-evidence-text">{candidate.evidence_summary}</p>
        )}
      </div>
    </div>
  );
}
