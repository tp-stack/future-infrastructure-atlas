interface FlagMeta {
  label: string;
  severity: "high" | "medium" | "low";
  recommendation: string;
}

interface Props {
  flags: string[];
  humanReviewRequired: boolean;
}

const FLAG_METADATA: Record<string, FlagMeta> = {
  GRID_CAPACITY_UNKNOWN: {
    label: "Grid capacity unknown",
    severity: "high",
    recommendation: "Utility interconnection study required before site commitment",
  },
  SUBSTATION_CAPACITY_ESTIMATED: {
    label: "Substation capacity estimated",
    severity: "medium",
    recommendation: "Obtain utility substation capacity data to confirm",
  },
  FIBER_AVAILABILITY_UNKNOWN: {
    label: "Fiber availability unknown",
    severity: "high",
    recommendation: "Carrier diversity audit and fiber route survey required",
  },
  ZONING_NOT_VERIFIED: {
    label: "Zoning not verified",
    severity: "high",
    recommendation: "Municipal zoning and permitting review required",
  },
  LAND_OWNERSHIP_UNKNOWN: {
    label: "Land ownership unknown",
    severity: "high",
    recommendation: "Title search and land acquisition feasibility study required",
  },
  PERMITTING_TIMELINE_UNKNOWN: {
    label: "Permitting timeline unknown",
    severity: "high",
    recommendation: "Regulatory pathway assessment required",
  },
  WATER_ACCESS_UNKNOWN: {
    label: "Water access unknown",
    severity: "high",
    recommendation: "Utility and hydrological study required",
  },
  COMMERCIAL_PPA_NOT_VERIFIED: {
    label: "Commercial PPA not verified",
    severity: "medium",
    recommendation: "Energy market analysis and PPA negotiation required",
  },
  CLIMATE_RISK_PROXY_ONLY: {
    label: "Climate risk proxy only",
    severity: "medium",
    recommendation: "Site-specific climate resilience study required",
  },
  REGULATORY_SCORE_COUNTRY_LEVEL_ONLY: {
    label: "Regulatory score country-level only",
    severity: "medium",
    recommendation: "Local regulatory and political risk assessment required",
  },
  MARKET_DEMAND_PROXY_ONLY: {
    label: "Market demand proxy only",
    severity: "medium",
    recommendation: "Commercial demand validation and offtake analysis required",
  },
  PROTECTED_AREA_PROXIMITY_OBSERVED: {
    label: "Protected area proximity observed",
    severity: "medium",
    recommendation: "Verify polygon boundaries and assess exclusion risk",
  },
  CABLE_LANDING_UNKNOWN: {
    label: "Submarine cable proximity unknown",
    severity: "medium",
    recommendation: "Submarine cable landing point survey required",
  },
};

const SEVERITY_CLASS: Record<string, string> = {
  high: "ss-flag-critical",
  medium: "ss-flag-warning",
  low: "ss-flag-info",
};

export default function MissingDataFlags({ flags, humanReviewRequired }: Props) {
  if (flags.length === 0 && !humanReviewRequired) return null;

  return (
    <div className="ss-flags-section">
      {humanReviewRequired && (
        <div className="ss-flag ss-flag-critical">
          HUMAN REVIEW REQUIRED — Confidence is limited or critical data is missing for this profile
        </div>
      )}
      {flags.map((flag) => {
        const meta = FLAG_METADATA[flag];
        if (!meta) {
          return (
            <div key={flag} className="ss-flag ss-flag-warning">
              {flag}
            </div>
          );
        }
        return (
          <div key={flag} className={`ss-flag ${SEVERITY_CLASS[meta.severity]}`}>
            <div className="ss-flag-header">
              <span className="ss-flag-label">{meta.label}</span>
              <span className={`ss-flag-severity ss-flag-severity--${meta.severity}`}>{meta.severity.toUpperCase()}</span>
            </div>
            <div className="ss-flag-recommendation">{meta.recommendation}</div>
          </div>
        );
      })}
    </div>
  );
}
