interface Props {
  flags: string[];
  humanReviewRequired: boolean;
}

const FLAG_LABELS: Record<string, string> = {
  GRID_CAPACITY_UNKNOWN: "Grid capacity unknown",
  SUBSTATION_CAPACITY_ESTIMATED: "Substation capacity estimated",
  FIBER_AVAILABILITY_UNKNOWN: "Fiber availability unknown",
  ZONING_NOT_VERIFIED: "Zoning not verified",
  LAND_OWNERSHIP_UNKNOWN: "Land ownership unknown",
  PERMITTING_TIMELINE_UNKNOWN: "Permitting timeline unknown",
  WATER_ACCESS_UNKNOWN: "Water access unknown",
  COMMERCIAL_PPA_NOT_VERIFIED: "Commercial PPA not verified",
  CLIMATE_RISK_PROXY_ONLY: "Climate risk proxy only",
  REGULATORY_SCORE_COUNTRY_LEVEL_ONLY: "Regulatory score country-level only",
  MARKET_DEMAND_PROXY_ONLY: "Market demand proxy only",
};

export default function MissingDataFlags({ flags, humanReviewRequired }: Props) {
  if (flags.length === 0 && !humanReviewRequired) return null;

  return (
    <div className="ss-flags-section">
      {humanReviewRequired && (
        <div className="ss-flag ss-flag-critical">
          HUMAN REVIEW REQUIRED — Confidence is limited or critical data is missing
        </div>
      )}
      {flags.map((flag) => (
        <div key={flag} className="ss-flag ss-flag-warning">
          {FLAG_LABELS[flag] || flag}
        </div>
      ))}
    </div>
  );
}
