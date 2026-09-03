import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { postJson } from "../api/fetchJson";

type Screen = {
  screen_id: string;
  version: string;
  description: string;
  filters: string;
  max_results: number;
};

type Candidate = {
  instrument_id: string;
  matched_reasons: string[];
  metrics: Record<string, unknown>;
  quality: string;
  inspection_priority: number;
  transition?: string;
};

type DiscoverRun = {
  available: boolean;
  candidate_set?: {
    screen_id: string;
    screen_version: string;
    received_at: string;
    candidate_count: number;
    candidates: Candidate[];
    quality: string;
  };
  screen?: Screen;
};

export function DiscoverPage() {
  const navigate = useNavigate();
  const [screens, setScreens] = useState<Screen[]>([]);
  const [selectedScreen, setSelectedScreen] = useState("SHORT_SQUEEZE_DISCOVERY");
  const [run, setRun] = useState<DiscoverRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScreens = async () => {
    const response = await fetch("/discover/screens");
    const payload = await response.json();
    setScreens(payload.screens ?? []);
  };

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/discover/run?screen=${encodeURIComponent(selectedScreen)}&force=1`,
      );
      const payload = (await response.json()) as DiscoverRun;
      setRun(payload);
      if (!payload.available) {
        setError(
          "Finviz discovery unavailable — authentication may be required. Run: python tools/finviz/auth.py status",
        );
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const promote = async (instrumentId: string) => {
    await postJson("/discover/promote-to-live-analysis", { instrument_id: instrumentId });
    navigate(`/workspace/${instrumentId}`);
  };

  useEffect(() => {
    void loadScreens();
  }, []);

  const candidateSet = run?.candidate_set;
  const candidates = candidateSet?.candidates ?? [];

  return (
    <div className="discover-page">
      <header className="discover-header">
        <h1>DISCOVER</h1>
        <p className="discover-subtitle">
          Finviz Elite broad-market discovery — candidates are INVESTIGATE, not trade signals.
        </p>
      </header>

      <div className="discover-controls">
        <label>
          Screen
          <select
            value={selectedScreen}
            onChange={(e) => setSelectedScreen(e.target.value)}
            onFocus={() => void loadScreens()}
          >
            {screens.length === 0 ? (
              <option value="SHORT_SQUEEZE_DISCOVERY">Short Squeeze Discovery v1</option>
            ) : (
              screens.map((screen) => (
                <option key={screen.screen_id} value={screen.screen_id}>
                  {screen.screen_id} v{screen.version}
                </option>
              ))
            )}
          </select>
        </label>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error ? <div className="discover-error" role="alert">{error}</div> : null}

      {candidateSet ? (
        <div className="discover-meta">
          <span>Preset: {candidateSet.screen_id} v{candidateSet.screen_version}</span>
          <span>Last refresh: {candidateSet.received_at}</span>
          <span>Candidates: {candidateSet.candidate_count}</span>
          <span>Quality: {candidateSet.quality}</span>
        </div>
      ) : null}

      <div className="discover-candidates">
        {candidates.map((candidate) => (
          <article key={candidate.instrument_id} className="discover-card">
            <div className="discover-card-header">
              <Link to={`/workspace/${candidate.instrument_id}`}>{candidate.instrument_id}</Link>
              {candidate.transition ? <span className="discover-transition">{candidate.transition}</span> : null}
            </div>
            <div className="discover-why">
              <strong>Why:</strong>
              {candidate.matched_reasons.join(" · ")}
            </div>
            <div className="discover-metrics">
              {candidate.metrics.rel_volume != null ? <span>RVOL {String(candidate.metrics.rel_volume)}</span> : null}
              {candidate.metrics.change_pct != null ? (
                <span>{Number(candidate.metrics.change_pct).toFixed(1)}%</span>
              ) : null}
              {candidate.metrics.short_float_pct != null ? (
                <span>Short {String(candidate.metrics.short_float_pct)}%</span>
              ) : null}
            </div>
            <div className="discover-card-footer">
              <span>Freshness: {candidateSet?.received_at ?? "—"}</span>
              <span>Quality: {candidate.quality}</span>
              <button type="button" onClick={() => void promote(candidate.instrument_id)}>
                Open Workspace
              </button>
            </div>
          </article>
        ))}
      </div>

      {run?.screen ? (
        <details className="discover-screen-inspector">
          <summary>Screen inspector</summary>
          <pre>{JSON.stringify(run.screen, null, 2)}</pre>
        </details>
      ) : null}
    </div>
  );
}
