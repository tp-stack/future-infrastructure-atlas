import { useState } from "react";
import type { CandidateSite } from "../../api/siteSelectionApi";
import SuitabilityScore from "./SuitabilityScore";
import RiskBreakdown from "./RiskBreakdown";
import MissingDataFlags from "./MissingDataFlags";
import DueDiligenceGapRegister from "./DueDiligenceGapRegister";
import ExecutiveSummary from "./ExecutiveSummary";

const EVIDENCE_WARNINGS: Record<string, string> = {
  grid: "Grid capacity unknown. Voltage proximity does not imply available MW.",
  fiber: "Fiber availability unconfirmed. Proximity does not guarantee carrier diversity.",
  land: "Zoning, ownership, brownfield status, and permitting timeline not verified.",
  climate: "Site-specific environmental assessment required.",
  water: "Water availability not confirmed. Cooling feasibility unknown.",
  regulatory: "Country-level score may not reflect local conditions.",
  market: "Market demand estimated from regional proxies only.",
};

interface Props {
  candidate: CandidateSite;
  onClose: () => void;
}

export default function EvidenceDrawer({ candidate, onClose }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="ss-evidence-drawer report-card">
      <div className="ss-evidence-header">
        <h3>Candidate #{candidate.rank}</h3>
        <button className="ss-evidence-close" onClick={onClose}>x</button>
      </div>

      <ExecutiveSummary candidate={candidate} />

      <div className="ss-evidence-location">
        {candidate.lat.toFixed(4)}, {candidate.lon.toFixed(4)}
        <span className="ss-evidence-location-detail">
          {" "}— {candidate.country}, {candidate.region}
        </span>
      </div>

      <div className="ss-evidence-scores">
        <SuitabilityScore
          label="Grid"
          score={candidate.grid_score}
          evidenceQuality={candidate.grid_evidence_quality}
          warning={EVIDENCE_WARNINGS.grid}
          size="small"
        />
        <SuitabilityScore
          label="Fiber"
          score={candidate.fiber_score}
          evidenceQuality={candidate.fiber_evidence_quality}
          warning={EVIDENCE_WARNINGS.fiber}
          size="small"
        />
        <SuitabilityScore
          label="Land"
          score={candidate.land_score}
          evidenceQuality={candidate.land_evidence_quality}
          warning={EVIDENCE_WARNINGS.land}
          size="small"
        />
        <SuitabilityScore
          label="Climate"
          score={candidate.climate_score}
          evidenceQuality={candidate.climate_evidence_quality}
          warning={EVIDENCE_WARNINGS.climate}
          size="small"
        />
        <SuitabilityScore
          label="Water"
          score={candidate.water_score}
          evidenceQuality={candidate.water_evidence_quality}
          warning={EVIDENCE_WARNINGS.water}
          size="small"
        />
        <SuitabilityScore
          label="Regulatory"
          score={candidate.regulatory_score}
          evidenceQuality={candidate.regulatory_evidence_quality}
          warning={EVIDENCE_WARNINGS.regulatory}
          size="small"
        />
        <SuitabilityScore
          label="Market"
          score={candidate.market_score}
          evidenceQuality={candidate.market_evidence_quality}
          warning={EVIDENCE_WARNINGS.market}
          size="small"
        />
      </div>

      <RiskBreakdown candidate={candidate} />
      <MissingDataFlags flags={candidate.missing_data_flags} humanReviewRequired={candidate.human_review_required} />

      {candidate.due_diligence_gaps && candidate.due_diligence_gaps.length > 0 && (
        <DueDiligenceGapRegister gaps={candidate.due_diligence_gaps} />
      )}

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
