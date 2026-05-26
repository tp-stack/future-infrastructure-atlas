import type { GapRegisterItem } from "../../api/siteSelectionApi";

interface Props {
  gaps: GapRegisterItem[];
}

const RISK_COLORS: Record<string, string> = {
  High: "#ef4444",
  Medium: "#f59e0b",
  Low: "#22c55e",
};

export default function DueDiligenceGapRegister({ gaps }: Props) {
  if (!gaps || gaps.length === 0) return null;

  return (
    <div className="gap-register">
      <div className="gap-register-header">Due Diligence Gap Register</div>
      <div className="gap-register-table">
        <div className="gap-register-row gap-register-row--header">
          <span className="gap-register-cell gap-register-cell--category">Category</span>
          <span className="gap-register-cell gap-register-cell--status">Status</span>
          <span className="gap-register-cell gap-register-cell--risk">Risk</span>
          <span className="gap-register-cell gap-register-cell--action">Action Required</span>
        </div>
        {gaps.map((gap) => (
          <div key={gap.flag_key} className="gap-register-row">
            <span className="gap-register-cell gap-register-cell--category">{gap.category}</span>
            <span className="gap-register-cell gap-register-cell--status">{gap.status}</span>
            <span
              className="gap-register-cell gap-register-cell--risk"
              style={{ color: RISK_COLORS[gap.risk] || "#6a6a72" }}
            >
              {gap.risk}
            </span>
            <span className="gap-register-cell gap-register-cell--action">{gap.action_required}</span>
          </div>
        ))}
      </div>
    </div>
  );
}