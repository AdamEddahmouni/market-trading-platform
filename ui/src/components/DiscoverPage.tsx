import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

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

type ProviderHealth = {
  provider: string;
  connection: string;
  role?: string;
  reason?: string | null;
  subscribed_candidates?: number;
};

type MixedCandidate = {
  instrument_id: string;
  candidate_role: "INVESTIGATE";
  lanes: string[];
  screen_matches: string[];
  matched_reasons: string[];
  metrics: Record<string, unknown>;
  discovery_as_of: string;
  quality: string;
  provenance: Array<Record<string, unknown>>;
  attention_score: number;
  attention_components: Record<string, number>;
  ranking_reasons: string[];
  supporting_evidence?: string[];
  caveats?: string[];
  market: {
    provider: string;
    status: "LIVE" | "DELAYED" | "SNAPSHOT" | "STALE" | "UNAVAILABLE";
    last_price?: number | null;
    bid_price?: number | null;
    ask_price?: number | null;
    spread_pct?: number | null;
    volume?: number | null;
    quality: string;
    reason?: string | null;
  };
  data_status: "LIVE" | "DELAYED" | "SNAPSHOT" | "STALE" | "UNAVAILABLE";
  freshness_label: string;
  queue_rank: number;
};

type MixedPayload = {
  available: boolean;
  mode: "SEMI_LIVE";
  candidate_role: "INVESTIGATE";
  execution_authority: "NONE";
  market_session?: string;
  generated_at: string;
  discovery_as_of: string | null;
  candidate_count?: number;
  live_subscription_summary?: { active: number; cap: number };
  refresh_in_progress: boolean;
  refresh_interval_seconds: number;
  poll_interval_seconds: number;
  provider_health: ProviderHealth[];
  lane_counts: Record<string, number>;
  screen_outcomes: Array<Record<string, unknown>>;
  candidates: MixedCandidate[];
};

type DiscoverMode = "MIXED" | "SINGLE";

function displayProvider(provider: string) {
  if (provider === "FINVIZ_ELITE") return "Finviz Elite";
  if (provider === "MOOMOO") return "Moomoo";
  return provider.replace(/_/g, " ");
}

function sourceBadge(provider: string) {
  return provider === "FINVIZ_ELITE" ? "FINVIZ ELITE" : provider.replace(/_/g, " ");
}

function formatNumber(value: unknown, digits = 2) {
  if (value == null || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";
}

function formatPercent(value: unknown, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}%` : "—";
}

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`.trim());
  return (await response.json()) as T;
}

export function DiscoverPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<DiscoverMode>("MIXED");
  const [activeLane, setActiveLane] = useState("ALL");
  const [mixed, setMixed] = useState<MixedPayload | null>(null);
  const [screens, setScreens] = useState<Screen[]>([]);
  const [selectedScreen, setSelectedScreen] = useState("SHORT_SQUEEZE_DISCOVERY");
  const [run, setRun] = useState<DiscoverRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScreens = useCallback(async () => {
    try {
      const payload = await readJson<{ screens?: Screen[] }>("/discover/screens");
      setScreens(payload.screens ?? []);
    } catch (err) {
      setError(String(err));
    }
  }, []);

  const readMixed = useCallback(async () => {
    try {
      const payload = await readJson<MixedPayload>("/discover/mixed", { method: "GET" });
      setMixed(payload);
      setError(null);
    } catch (err) {
      setError(`Mixed screener read unavailable: ${String(err)}`);
    }
  }, []);

  const refreshMixed = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await readJson<MixedPayload>("/discover/mixed/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      setMixed(payload);
      setError(null);
    } catch (err) {
      setError(`Mixed screener refresh unavailable: ${String(err)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSingle = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await readJson<DiscoverRun>(
        `/discover/run?screen=${encodeURIComponent(selectedScreen)}&force=1`,
      );
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
    try {
      await readJson("/discover/promote-to-live-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instrument_id: instrumentId }),
      });
      navigate(`/workspace/${instrumentId}`);
    } catch (err) {
      setError(`Workspace promotion failed: ${String(err)}`);
    }
  };

  useEffect(() => {
    if (mode !== "MIXED") return;
    if (!document.hidden) {
      void readMixed().then(() => refreshMixed());
    }
  }, [mode, readMixed, refreshMixed]);

  useEffect(() => {
    if (mode !== "MIXED") return;
    return () => {
      void fetch(new URL("/discover/mixed/release", window.location.href), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
        keepalive: true,
      });
    };
  }, [mode]);

  useEffect(() => {
    if (mode !== "MIXED") return;
    let pollTimer: number | undefined;
    let refreshTimer: number | undefined;
    const pollMs = (mixed?.poll_interval_seconds ?? 3) * 1_000;
    const refreshMs = (mixed?.refresh_interval_seconds ?? 120) * 1_000;

    const stopTimers = () => {
      if (pollTimer !== undefined) window.clearInterval(pollTimer);
      if (refreshTimer !== undefined) window.clearInterval(refreshTimer);
      pollTimer = undefined;
      refreshTimer = undefined;
    };
    const startTimers = () => {
      stopTimers();
      if (document.hidden) return;
      pollTimer = window.setInterval(() => void readMixed(), pollMs);
      refreshTimer = window.setInterval(() => void refreshMixed(), refreshMs);
    };
    const handleVisibility = () => {
      startTimers();
      if (!document.hidden) void readMixed();
    };

    startTimers();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      stopTimers();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [mode, mixed?.poll_interval_seconds, mixed?.refresh_interval_seconds, readMixed, refreshMixed]);

  useEffect(() => {
    if (mode === "SINGLE" && screens.length === 0) void loadScreens();
  }, [loadScreens, mode, screens.length]);

  const candidateSet = run?.candidate_set;
  const singleCandidates = candidateSet?.candidates ?? [];
  const mixedCandidates = mixed?.candidates ?? [];
  const visibleMixedCandidates = activeLane === "ALL"
    ? mixedCandidates
    : mixedCandidates.filter((candidate) => candidate.lanes.includes(activeLane));
  const degradedScreens = (mixed?.screen_outcomes ?? []).filter((row) => row.status !== "PASS");

  return (
    <div className="discover-page">
      <header className="discover-header">
        <div>
          <p className="discover-eyebrow">DISCOVERY DESK</p>
          <h1>Mixed live screener</h1>
          <p className="discover-subtitle">
            Finviz finds the setup. Connected market data confirms what is happening now.
          </p>
        </div>
        <div className="discover-authority" aria-label="Screener execution boundary">
          <span>SEMI-LIVE DATA</span>
          <strong>EXEC NONE · INVESTIGATE only</strong>
        </div>
      </header>

      <nav className="discover-mode-switch" aria-label="Discovery mode">
        <button type="button" aria-pressed={mode === "MIXED"} onClick={() => setMode("MIXED")}>
          Mixed Live
        </button>
        <button type="button" aria-pressed={mode === "SINGLE"} onClick={() => setMode("SINGLE")}>
          Single Screen
        </button>
      </nav>

      <p className="discover-disclosure">Candidates are INVESTIGATE, not trade signals.</p>

      {error ? <div className="discover-error" role="alert">{error}</div> : null}

      {mode === "MIXED" ? (
        <section aria-label="Mixed live discovery queue">
          <div className="discover-live-banner" aria-label="Live screener status">
            <span className="discover-session">
              {mixed?.market_session?.replace(/_/g, " ") ?? "SESSION —"}
            </span>
            <span>
              Candidates <strong>{mixed?.candidate_count ?? mixedCandidates.length}</strong>
            </span>
            {mixed?.live_subscription_summary ? (
              <span>
                Live quotes{" "}
                <strong>
                  {mixed.live_subscription_summary.active} / {mixed.live_subscription_summary.cap}
                </strong>
              </span>
            ) : null}
            <span className="discover-exec-none">EXEC {mixed?.execution_authority ?? "NONE"}</span>
          </div>
          <div className="discover-status-strip">
            <div className="discover-provider-health" aria-label="Provider health">
              {(mixed?.provider_health ?? []).map((provider) => (
                <span key={provider.provider} className={`provider-state provider-${provider.connection.toLowerCase()}`}>
                  <i aria-hidden="true" />
                  {displayProvider(provider.provider)} <strong>{provider.connection}</strong>
                  {provider.subscribed_candidates != null ? ` · ${provider.subscribed_candidates} quotes` : ""}
                </span>
              ))}
              {!mixed ? <span className="provider-state">Connecting discovery sources…</span> : null}
            </div>
            <button type="button" onClick={() => void refreshMixed()} disabled={loading || mixed?.refresh_in_progress}>
              {loading || mixed?.refresh_in_progress ? "Refreshing discovery…" : "Refresh all screens"}
            </button>
          </div>

          {degradedScreens.length > 0 ? (
            <details className="discover-screen-outcomes">
              <summary>{degradedScreens.length} discovery screen(s) degraded or using saved captures</summary>
              <ul>
                {degradedScreens.map((row) => (
                  <li key={String(row.screen_id)}>
                    {String(row.screen_id)} · {String(row.status)}
                    {row.reason ? ` · ${String(row.reason)}` : ""}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <div className="discover-lane-summary" aria-label="Candidate lanes">
            <button type="button" aria-label="ALL" aria-pressed={activeLane === "ALL"} onClick={() => setActiveLane("ALL")}>
              ALL <strong>{mixedCandidates.length}</strong>
            </button>
            {Object.entries(mixed?.lane_counts ?? {}).map(([lane, count]) => (
              <button
                key={lane}
                type="button"
                aria-label={lane}
                aria-pressed={activeLane === lane}
                onClick={() => setActiveLane(lane)}
              >
                {lane} <strong>{count}</strong>
              </button>
            ))}
            <span className="discover-as-of">
              Discovery {mixed?.discovery_as_of ?? "awaiting snapshot"} · Market poll every {mixed?.poll_interval_seconds ?? 3}s
            </span>
          </div>

          <div className="discover-queue" aria-live="polite">
            {visibleMixedCandidates.map((candidate) => (
              <article
                key={candidate.instrument_id}
                className={`discover-queue-row data-${candidate.data_status.toLowerCase()}`}
              >
                <div className="discover-rank" aria-label={`Queue rank ${candidate.queue_rank}`}>
                  {String(candidate.queue_rank).padStart(2, "0")}
                </div>
                <div className="discover-instrument">
                  <strong className="discover-symbol">{candidate.instrument_id}</strong>
                  <span className="discover-score">ATTN {formatNumber(candidate.attention_score, 1)}</span>
                  <div className="discover-lanes">
                    {candidate.lanes.map((lane) => <span key={lane}>{lane}</span>)}
                  </div>
                </div>
                <div className="discover-market">
                  <strong>${formatNumber(candidate.market.last_price)}</strong>
                  <span>
                    {formatPercent(candidate.metrics.change_pct)}
                    {candidate.data_status === "LIVE" ? " snapshot chg" : ""}
                  </span>
                  <span>RVOL {formatNumber(candidate.metrics.rel_volume)}</span>
                  <span>Spread {formatPercent(candidate.market.spread_pct)}</span>
                  <span>Vol {formatNumber(candidate.market.volume ?? candidate.metrics.volume, 0)}</span>
                </div>
                <div className="discover-sources">
                  {candidate.data_status !== "LIVE" ? (
                    <span className="source-badge">FINVIZ SNAPSHOT</span>
                  ) : null}
                  {candidate.market.provider !== "FINVIZ_ELITE" && candidate.data_status === "LIVE" ? (
                    <span className={`source-badge source-${candidate.data_status.toLowerCase()}`}>
                      {sourceBadge(candidate.market.provider)} {candidate.data_status}
                    </span>
                  ) : null}
                  {candidate.market.reason && candidate.data_status !== "LIVE" ? (
                    <span className="source-badge source-unavailable">{String(candidate.market.reason)}</span>
                  ) : null}
                </div>
                <div className="discover-data-state">
                  <span className="data-status-pill">
                    {candidate.data_status}
                    {candidate.data_status !== "SNAPSHOT" && candidate.data_status !== "UNAVAILABLE"
                      ? ` · ${candidate.freshness_label}`
                      : ""}
                  </span>
                  {candidate.market.bid_price != null && candidate.market.ask_price != null ? (
                    <span>{formatNumber(candidate.market.bid_price)} × {formatNumber(candidate.market.ask_price)}</span>
                  ) : null}
                </div>
                <div className="discover-row-actions">
                  <button type="button" onClick={() => void promote(candidate.instrument_id)}>Open Workspace</button>
                  <details>
                    <summary>Evidence</summary>
                    <div className="discover-evidence">
                      <p><strong>Why:</strong> {(candidate.supporting_evidence ?? candidate.matched_reasons).join(" · ")}</p>
                      <p><strong>Ranking:</strong> {candidate.ranking_reasons.join(" · ")}</p>
                      <p><strong>Screens:</strong> {candidate.screen_matches.join(" · ")}</p>
                      {candidate.caveats && candidate.caveats.length > 0 ? (
                        <p><strong>Caveats:</strong> {candidate.caveats.join(" · ")}</p>
                      ) : null}
                      <pre>{JSON.stringify(candidate.attention_components, null, 2)}</pre>
                    </div>
                  </details>
                </div>
              </article>
            ))}
          </div>

          {mixed && mixed.candidates.length === 0 ? (
            <div className="discover-empty">No eligible candidates in the latest discovery captures.</div>
          ) : null}
        </section>
      ) : (
        <section aria-label="Single screen diagnostics">
          <div className="discover-controls">
            <label>
              Screen
              <select
                value={selectedScreen}
                onChange={(event) => setSelectedScreen(event.target.value)}
                onFocus={() => void loadScreens()}
              >
                {screens.length === 0 ? (
                  <option value="SHORT_SQUEEZE_DISCOVERY">Short Squeeze Discovery v1</option>
                ) : screens.map((screen) => (
                  <option key={screen.screen_id} value={screen.screen_id}>
                    {screen.screen_id} v{screen.version}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={() => void refreshSingle()} disabled={loading}>
              {loading ? "Refreshing…" : "Refresh screen"}
            </button>
          </div>

          {candidateSet ? (
            <div className="discover-meta">
              <span>Preset: {candidateSet.screen_id} v{candidateSet.screen_version}</span>
              <span>Last refresh: {candidateSet.received_at}</span>
              <span>Candidates: {candidateSet.candidate_count}</span>
              <span>Quality: {candidateSet.quality}</span>
            </div>
          ) : null}

          <div className="discover-candidates">
            {singleCandidates.map((candidate) => (
              <article key={candidate.instrument_id} className="discover-card">
                <div className="discover-card-header">
                  <Link to={`/workspace/${candidate.instrument_id}`}>{candidate.instrument_id}</Link>
                  {candidate.transition ? <span className="discover-transition">{candidate.transition}</span> : null}
                </div>
                <div className="discover-why"><strong>Why:</strong> {candidate.matched_reasons.join(" · ")}</div>
                <div className="discover-metrics">
                  {candidate.metrics.rel_volume != null ? <span>RVOL {String(candidate.metrics.rel_volume)}</span> : null}
                  {candidate.metrics.change_pct != null ? <span>{formatPercent(candidate.metrics.change_pct)}</span> : null}
                  {candidate.metrics.short_float_pct != null ? <span>Short {formatPercent(candidate.metrics.short_float_pct)}</span> : null}
                </div>
                <div className="discover-card-footer">
                  <span>Freshness: {candidateSet?.received_at ?? "—"}</span>
                  <span>Quality: {candidate.quality}</span>
                  <button type="button" onClick={() => void promote(candidate.instrument_id)}>Open Workspace</button>
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
        </section>
      )}
    </div>
  );
}
