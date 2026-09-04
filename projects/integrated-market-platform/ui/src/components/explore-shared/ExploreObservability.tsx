import { Link } from "react-router-dom";
import {
  useExploreFuturesQuery,
  useExploreCatalystQuery,
  useExploreSqueezeQuery,
  useExploreSqueezeScannerQuery,
} from "../../api/hooks";
import { ADMITTED_CATALYST_INSTRUMENT_ID, ADMITTED_FUTURES_INSTRUMENT_ID } from "../../api/schemas";
import { CountBarChartPanel } from "../charts/ResearchChartPanels";
import { LiveObservationalPanel } from "../live/LiveObservationalPanel";

export type ExploreObservabilityProps = {
  onExplain?: (ref: string) => void;
  showLivePanel?: boolean;
};

function formatProvenanceValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) return value.map((item) => formatProvenanceValue(item)).join(", ");
  return JSON.stringify(value);
}

type ExploreTableProps = {
  rows: Array<{
    screener_id: string;
    symbol: string;
    outcome_status: string;
    evidence_coverage: string;
    research_detection: string;
    freshness: string;
    scanner_rank?: number | null;
    explanation_ref?: string;
  }>;
  workspacePath: (symbol: string) => string;
  onExplain?: (ref: string) => void;
  showScannerRank?: boolean;
};

function ExploreSqueezeTable({ rows, workspacePath, onExplain, showScannerRank = false }: ExploreTableProps) {
  return (
    <table className="explore-table">
      <thead>
        <tr>
          {showScannerRank ? <th>Rank</th> : null}
          <th>Symbol</th>
          <th>Outcome</th>
          <th>Evidence</th>
          <th>Detection</th>
          <th>Freshness</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.screener_id}>
            {showScannerRank ? <td>{row.scanner_rank ?? "—"}</td> : null}
            <td>
              <Link className="explore-symbol-link" to={workspacePath(row.symbol)}>
                {row.symbol}
              </Link>
            </td>
            <td>{row.outcome_status}</td>
            <td>{row.evidence_coverage}</td>
            <td>{row.research_detection}</td>
            <td>{row.freshness}</td>
            <td>
              {row.explanation_ref && onExplain ? (
                <button
                  type="button"
                  className="explore-explain-link"
                  onClick={() => onExplain(row.explanation_ref!)}
                >
                  Explain
                </button>
              ) : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const SCANNER_PLACEHOLDER_DISCLAIMER =
  "Ephemeral provider scanner snapshot. Not the frozen research cohort.";

export function ExploreObservability({ onExplain, showLivePanel = false }: ExploreObservabilityProps) {
  const squeezeQuery = useExploreSqueezeQuery();
  const scannerQuery = useExploreSqueezeScannerQuery();
  const futuresQuery = useExploreFuturesQuery();
  const catalystQuery = useExploreCatalystQuery();

  if (squeezeQuery.isLoading || scannerQuery.isLoading) {
    return <div className="app-loading">Loading donor screener bridge…</div>;
  }

  const payload = squeezeQuery.data;
  const scannerPayload = scannerQuery.data;
  if (!payload) {
    return (
      <div className="capability-panel unavailable">
        <p>Donor screener bridge unavailable.</p>
      </div>
    );
  }

  return (
    <>
      {showLivePanel ? <LiveObservationalPanel /> : null}

      <section className="explore-section">
        <h2>Short Squeeze Screener (read-only bridge)</h2>
        <h3>Frozen research cohort</h3>
        <p className="explore-disclaimer">{payload.disclaimer ?? "Research only."}</p>
        {!payload.available ? (
          <div className="capability-panel unavailable">
            <p>{payload.reason ?? "Donor server unavailable."}</p>
          </div>
        ) : (
          <>
            <p className="explore-meta">
              Source: {payload.source} · Rows: {payload.row_count} · Mode: FROZEN_RESEARCH
            </p>
            {payload.manifest ? (
              <dl className="explore-provenance-grid">
                <div>
                  <dt>Donor API</dt>
                  <dd>{formatProvenanceValue(payload.manifest.api_version)}</dd>
                </div>
                <div>
                  <dt>Schema</dt>
                  <dd>{formatProvenanceValue(payload.manifest.schema_version)}</dd>
                </div>
                <div>
                  <dt>Prohibited capabilities</dt>
                  <dd>{formatProvenanceValue(payload.manifest.prohibited_capabilities)}</dd>
                </div>
              </dl>
            ) : null}
            {payload.outcome_summary && payload.outcome_summary.length > 0 ? (
              <div className="chart-grid chart-grid-inline">
                <CountBarChartPanel
                  title="Squeeze outcome distribution"
                  series={payload.outcome_summary}
                  provenance={{
                    source: payload.source,
                    method: "donor frozen screener aggregation",
                  }}
                  ariaLabel="Squeeze outcome distribution chart"
                />
              </div>
            ) : null}
            <ExploreSqueezeTable
              rows={payload.rows}
              workspacePath={(symbol) => `/workspace/${symbol}/squeeze`}
              onExplain={onExplain}
            />
          </>
        )}
      </section>

      <section className="explore-section">
        <h2>Live provider scanner</h2>
        <p className="explore-disclaimer">{scannerPayload?.disclaimer ?? SCANNER_PLACEHOLDER_DISCLAIMER}</p>
        {!scannerPayload?.available ? (
          <div className="capability-panel unavailable">
            <p>{scannerPayload?.reason ?? "Live scanner bridge unavailable."}</p>
          </div>
        ) : (
          <>
            <p className="explore-meta">
              Source: {scannerPayload.source} · Rows: {scannerPayload.row_count}
              {scannerPayload.donor_deployment_mode
                ? ` · Donor mode: ${scannerPayload.donor_deployment_mode}`
                : ""}
            </p>
            {scannerPayload.empty_reason ? (
              <p className="explore-header-note">{scannerPayload.empty_reason}</p>
            ) : null}
            {scannerPayload.detection_summary && scannerPayload.detection_summary.length > 0 ? (
              <div className="chart-grid chart-grid-inline">
                <CountBarChartPanel
                  title="Scanner detection distribution"
                  series={scannerPayload.detection_summary}
                  provenance={{
                    source: scannerPayload.source,
                    method: "donor current scanner aggregation",
                  }}
                  ariaLabel="Scanner detection distribution chart"
                />
              </div>
            ) : null}
            {scannerPayload.rows.length > 0 ? (
              <ExploreSqueezeTable
                rows={scannerPayload.rows}
                workspacePath={(symbol) => `/workspace/${symbol}/squeeze?data_mode=current`}
                onExplain={onExplain}
                showScannerRank
              />
            ) : (
              <p>No current scanner candidates. Run discovery on the donor screener.</p>
            )}
          </>
        )}
      </section>

      <section className="explore-section">
        <h2>ES Futures depth bridge</h2>
        {futuresQuery.isLoading ? (
          <p>Loading futures bridge status…</p>
        ) : (
          <>
            <p className="explore-disclaimer">
              {futuresQuery.data?.disclaimer ?? "Read-only FuturesX bridge for ES depth snapshots."}
            </p>
            {!futuresQuery.data?.available ? (
              <div className="capability-panel unavailable">
                <p>{futuresQuery.data?.reason ?? "FuturesX donor bridge unavailable."}</p>
              </div>
            ) : (
              <>
                <p className="explore-meta">
                  Symbol: {futuresQuery.data.symbol} · Bridge: {futuresQuery.data.bridge_url ?? "—"}
                  {futuresQuery.data.mode ? ` · Mode: ${futuresQuery.data.mode}` : ""}
                  {futuresQuery.data.contract_month
                    ? ` · Contract: ${futuresQuery.data.contract_month}`
                    : ""}
                  {futuresQuery.data.latest_imbalance_signal
                    ? ` · Signal: ${futuresQuery.data.latest_imbalance_signal}`
                    : ""}
                  {futuresQuery.data.snapshot_source
                    ? ` · Source: ${futuresQuery.data.snapshot_source}`
                    : ""}
                </p>
                <p>
                  <Link
                    className="explore-symbol-link"
                    to={`/workspace/${ADMITTED_FUTURES_INSTRUMENT_ID}/futures`}
                  >
                    Open {ADMITTED_FUTURES_INSTRUMENT_ID} futures workspace
                  </Link>
                  {onExplain ? (
                    <>
                      {" · "}
                      <button
                        type="button"
                        className="explore-explain-link"
                        onClick={() => onExplain(`explain:futures:${ADMITTED_FUTURES_INSTRUMENT_ID}`)}
                      >
                        Explain
                      </button>
                    </>
                  ) : null}
                </p>
              </>
            )}
          </>
        )}
      </section>

      <section className="explore-section">
        <h2>Catalyst bridge</h2>
        {catalystQuery.isLoading ? (
          <p>Loading catalyst bridge status…</p>
        ) : (
          <>
            <p className="explore-disclaimer">
              {catalystQuery.data?.disclaimer ??
                "Read-only internship demo state for public catalyst signals."}
            </p>
            {!catalystQuery.data?.available ? (
              <div className="capability-panel unavailable">
                <p>{catalystQuery.data?.reason ?? "Internship demo state unavailable."}</p>
                <p className="workspace-hint">
                  Seed demo state: run <code>python scripts/seed_demo_state.py</code> in{" "}
                  <code>news_momentum_agent/</code>.
                </p>
              </div>
            ) : (
              <>
                <p className="explore-meta">
                  Source: {catalystQuery.data.source} · Rows: {catalystQuery.data.row_count}
                  {catalystQuery.data.demo_mode ? " · Demo mode" : ""}
                </p>
                {catalystQuery.data.decision_summary && catalystQuery.data.decision_summary.length > 0 ? (
                  <div className="chart-grid chart-grid-inline">
                    <CountBarChartPanel
                      title="Catalyst decision distribution"
                      series={catalystQuery.data.decision_summary}
                      provenance={{
                        source: catalystQuery.data.source ?? "internship-project-main",
                        method: "donor catalyst aggregation",
                      }}
                      ariaLabel="Catalyst decision distribution chart"
                    />
                  </div>
                ) : null}
                {catalystQuery.data.rows && catalystQuery.data.rows.length > 0 ? (
                  <table className="explore-table">
                    <thead>
                      <tr>
                        <th>Symbol</th>
                        <th>Decision</th>
                        <th>Headline</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {catalystQuery.data.rows.map((row) => (
                        <tr key={row.catalyst_id}>
                          <td>
                            <Link className="explore-symbol-link" to={`/workspace/${row.symbol}/catalyst`}>
                              {row.symbol}
                            </Link>
                          </td>
                          <td>{row.decision ?? "—"}</td>
                          <td>{row.headline ?? "—"}</td>
                          <td>
                            {row.explanation_ref && onExplain ? (
                              <button
                                type="button"
                                className="explore-explain-link"
                                onClick={() => onExplain(row.explanation_ref!)}
                              >
                                Explain
                              </button>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p>No catalyst rows in demo state.</p>
                )}
                <p>
                  <Link
                    className="explore-symbol-link"
                    to={`/workspace/${ADMITTED_CATALYST_INSTRUMENT_ID}/catalyst`}
                  >
                    Open {ADMITTED_CATALYST_INSTRUMENT_ID} catalyst workspace
                  </Link>
                </p>
              </>
            )}
          </>
        )}
      </section>
    </>
  );
}
