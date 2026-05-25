import { useState, useEffect, useCallback } from "react";
import type { ComputeProfile, ScoringProfile, CandidateSite, QueryArea } from "../../api/siteSelectionApi";
import { fetchProfiles, queryCandidates } from "../../api/siteSelectionApi";
import CandidateLocationCard from "./CandidateLocationCard";
import EvidenceDrawer from "./EvidenceDrawer";

interface Props {
  baseUrl?: string;
  mapBounds?: [number, number, number, number] | null;
  onCandidatesGenerated?: (candidates: CandidateSite[]) => void;
}

export default function SiteSelectionPanel({ baseUrl = "/api", mapBounds, onCandidatesGenerated }: Props) {
  const [profiles, setProfiles] = useState<ComputeProfile[]>([]);
  const [scoringProfiles, setScoringProfiles] = useState<ScoringProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("regional_compute_5mw");
  const [selectedScoringProfile, setSelectedScoringProfile] = useState("default");
  const [limit, setLimit] = useState(25);
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [candidates, setCandidates] = useState<CandidateSite[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSite | null>(null);
  const [queryHistory, setQueryHistory] = useState<{ area: string; time: string }[]>([]);

  useEffect(() => {
    fetchProfiles(baseUrl)
      .then((res) => {
        setProfiles(res.compute_profiles);
        setScoringProfiles(res.scoring_profiles);
      })
      .catch((err) => setError(`Failed to load profiles: ${err.message}`));
  }, [baseUrl]);

  const handleGenerate = useCallback(async () => {
    if (!mapBounds) {
      setError("No map bounds available. Please zoom to an area first.");
      return;
    }

    setLoading(true);
    setError(null);
    setCandidates([]);

    const area: QueryArea = {
      type: "bbox",
      coordinates: mapBounds,
    };

    try {
      const result = await queryCandidates(
        baseUrl,
        area,
        selectedProfile,
        selectedScoringProfile,
        limit,
        includeExcluded,
      );
      setCandidates(result.candidates);
      onCandidatesGenerated?.(result.candidates);
      setQueryHistory((prev) => [
        { area: mapBounds.map((c) => c.toFixed(2)).join(", "), time: new Date().toLocaleTimeString() },
        ...prev.slice(0, 9),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }, [baseUrl, mapBounds, selectedProfile, selectedScoringProfile, limit, includeExcluded]);

  const handleExportJson = useCallback(() => {
    if (candidates.length === 0) return;
    const blob = new Blob([JSON.stringify({ candidates, generated_at: new Date().toISOString() }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `site-selection-candidates.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [candidates]);

  const handleExportCsv = useCallback(() => {
    if (candidates.length === 0) return;
    const headers = ["rank", "candidate_site_id", "lat", "lon", "country", "region", "final_score", "confidence_score"];
    const rows = candidates.map((c) => [c.rank, c.candidate_site_id, c.lat, c.lon, c.country, c.region, c.final_score, c.confidence_score]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `site-selection-candidates.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [candidates]);

  return (
    <div className="panel-section">
      <h2>Compute Site Selection</h2>

      <div className="ss-control-group">
        <label className="ss-label">Compute profile</label>
        <select
          className="ss-select"
          value={selectedProfile}
          onChange={(e) => setSelectedProfile(e.target.value)}
        >
          {profiles.map((p) => (
            <option key={p.key} value={p.key}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="ss-control-group">
        <label className="ss-label">Scoring profile</label>
        <select
          className="ss-select"
          value={selectedScoringProfile}
          onChange={(e) => setSelectedScoringProfile(e.target.value)}
        >
          {scoringProfiles.map((p) => (
            <option key={p.key} value={p.key}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="ss-control-group">
        <label className="ss-label">Limit: {limit}</label>
        <input
          type="range"
          className="ss-range"
          min={5}
          max={100}
          step={5}
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        />
      </div>

      <div className="ss-control-row">
        <label className="ss-checkbox-label">
          <input
            type="checkbox"
            checked={includeExcluded}
            onChange={(e) => setIncludeExcluded(e.target.checked)}
          />
          Include excluded
        </label>
      </div>

      <button
        className="ss-generate-btn"
        onClick={handleGenerate}
        disabled={loading || !mapBounds}
      >
        {loading ? "Generating..." : "Generate Candidate Locations"}
      </button>

      {!mapBounds && (
        <div className="ss-hint">Zoom to an area on the map to enable candidate generation.</div>
      )}

      {error && <div className="ss-error">{error}</div>}

      {candidates.length > 0 && (
        <div className="ss-results-toolbar">
          <button className="ss-export-btn" onClick={handleExportJson}>Export JSON</button>
          <button className="ss-export-btn" onClick={handleExportCsv}>Export CSV</button>
          <span className="ss-result-count">{candidates.length} candidates</span>
        </div>
      )}

      <div className="ss-candidate-list">
        {candidates.map((c) => (
          <CandidateLocationCard
            key={c.candidate_site_id}
            candidate={c}
            onSelect={setSelectedCandidate}
          />
        ))}
      </div>

      {queryHistory.length > 0 && (
        <div className="ss-query-history">
          <h3>Recent queries</h3>
          {queryHistory.map((q, i) => (
            <div key={i} className="ss-query-history-item">
              <span className="ss-query-history-area">{q.area}</span>
              <span className="ss-query-history-time">{q.time}</span>
            </div>
          ))}
        </div>
      )}

      {selectedCandidate && (
        <div className="ss-evidence-overlay" onClick={() => setSelectedCandidate(null)}>
          <div className="ss-evidence-overlay-content" onClick={(e) => e.stopPropagation()}>
            <EvidenceDrawer candidate={selectedCandidate} onClose={() => setSelectedCandidate(null)} />
          </div>
        </div>
      )}
    </div>
  );
}
