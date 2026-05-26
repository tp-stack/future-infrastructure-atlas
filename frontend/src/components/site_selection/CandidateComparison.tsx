import { useState, useMemo } from "react";
import type { CandidateSite } from "../../api/siteSelectionApi";

interface Props {
  candidates: CandidateSite[];
  onClose: () => void;
}

const DIMENSIONS = [
  { key: "grid_score", label: "Grid" },
  { key: "fiber_score", label: "Fiber" },
  { key: "land_score", label: "Land" },
  { key: "climate_score", label: "Climate" },
  { key: "water_score", label: "Water" },
  { key: "regulatory_score", label: "Regulatory" },
  { key: "market_score", label: "Market" },
] as const;

function scoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#d69a13";
  if (score >= 40) return "#f59e0b";
  return "#ef4444";
}

export default function CandidateComparison({ candidates, onClose }: Props) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    new Set(candidates.slice(0, 3).map((c) => c.candidate_site_id))
  );

  const toggle = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const visible = useMemo(
    () => candidates.filter((c) => selectedIds.has(c.candidate_site_id)),
    [candidates, selectedIds]
  );

  if (candidates.length === 0) return null;

  return (
    <div className="ss-evidence-overlay" onClick={onClose}>
      <div className="candidate-comparison" onClick={(e) => e.stopPropagation()}>
        <div className="candidate-comparison-header">
          <h3>Compare Candidates</h3>
          <button className="ss-evidence-close" onClick={onClose}>x</button>
        </div>

        <div className="candidate-comparison-selector">
          {candidates.map((c) => (
            <label key={c.candidate_site_id} className="candidate-comparison-chip">
              <input
                type="checkbox"
                checked={selectedIds.has(c.candidate_site_id)}
                onChange={() => toggle(c.candidate_site_id)}
              />
              <span>#{c.rank} — {c.country}</span>
              <span className="candidate-comparison-chip-score" style={{ color: scoreColor(c.final_score) }}>
                {c.final_score.toFixed(0)}
              </span>
            </label>
          ))}
        </div>

        {visible.length > 0 && (
          <div className="candidate-comparison-table-wrapper">
            <table className="candidate-comparison-table">
              <thead>
                <tr>
                  <th className="candidate-comparison-th">Dimension</th>
                  {visible.map((c) => (
                    <th key={c.candidate_site_id} className="candidate-comparison-th">
                      #{c.rank}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="candidate-comparison-td candidate-comparison-td--label">Final Score</td>
                  {visible.map((c) => (
                    <td
                      key={c.candidate_site_id}
                      className="candidate-comparison-td"
                      style={{ color: scoreColor(c.final_score), fontWeight: 700 }}
                    >
                      {c.final_score.toFixed(0)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="candidate-comparison-td candidate-comparison-td--label">Confidence</td>
                  {visible.map((c) => (
                    <td key={c.candidate_site_id} className="candidate-comparison-td">
                      {c.confidence_score.toFixed(0)}
                    </td>
                  ))}
                </tr>
                {DIMENSIONS.map((dim) => (
                  <tr key={dim.key}>
                    <td className="candidate-comparison-td candidate-comparison-td--label">{dim.label}</td>
                    {visible.map((c) => {
                      const val = c[dim.key as keyof CandidateSite] as number;
                      return (
                        <td
                          key={c.candidate_site_id}
                          className="candidate-comparison-td"
                          style={{ color: scoreColor(val) }}
                        >
                          {val.toFixed(0)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr>
                  <td className="candidate-comparison-td candidate-comparison-td--label">Substation</td>
                  {visible.map((c) => (
                    <td key={c.candidate_site_id} className="candidate-comparison-td">
                      {c.nearest_substation_km !== null ? `${c.nearest_substation_km.toFixed(1)} km` : "—"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="candidate-comparison-td candidate-comparison-td--label">Fiber</td>
                  {visible.map((c) => (
                    <td key={c.candidate_site_id} className="candidate-comparison-td">
                      {c.nearest_fiber_km !== null ? `${c.nearest_fiber_km.toFixed(1)} km` : "—"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="candidate-comparison-td candidate-comparison-td--label">Flags</td>
                  {visible.map((c) => (
                    <td key={c.candidate_site_id} className="candidate-comparison-td">
                      {c.missing_data_flags.length}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="candidate-comparison-td candidate-comparison-td--label">Review</td>
                  {visible.map((c) => (
                    <td key={c.candidate_site_id} className="candidate-comparison-td">
                      {c.human_review_required ? "⚠" : "—"}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {visible.length === 0 && (
          <div className="candidate-comparison-empty">Select candidates above to compare</div>
        )}
      </div>
    </div>
  );
}