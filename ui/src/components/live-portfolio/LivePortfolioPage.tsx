import { Link } from "react-router-dom";
import type { LiveCanarySnapshot } from "../live-now/liveCanarySnapshot";
import {
  livePortfolioMetrics,
  livePortfolioOrders,
  livePortfolioPositions,
  liveProgramCapMetrics,
} from "./livePortfolioViewModel";

type ReconciliationPayload = {
  reconciliation_health: string;
  local_open_orders: string[];
  ambiguous_states: string[];
};

type Props = {
  snapshot?: LiveCanarySnapshot;
  reconciliation?: ReconciliationPayload;
  state: "loading" | "ready" | "error";
};

export function LivePortfolioPage({ snapshot, reconciliation, state }: Props) {
  const positions = livePortfolioPositions(snapshot);
  const orders = livePortfolioOrders(snapshot);
  const ambiguous =
    reconciliation?.ambiguous_states ?? snapshot?.ambiguous_states ?? [];

  return (
    <section className="page portfolio-page live-portfolio-page">
      <header className="live-portfolio-header">
        <div>
          <span className="live-eyebrow">Live · broker-observed read-only</span>
          <h1>Live Portfolio</h1>
          <p>
            Broker-reported positions and open orders for operational safety review. This view never
            exposes execution controls.
          </p>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      {state === "loading" ? <p role="status">Loading broker portfolio snapshot…</p> : null}
      {state === "error" ? (
        <div className="capability-panel unavailable">
          <p>Broker portfolio snapshot unavailable.</p>
        </div>
      ) : null}

      {state === "ready" && snapshot ? (
        <>
          <section className="live-panel live-portfolio-summary" aria-label="Account summary">
            <h2>Account summary</h2>
            <dl className="live-safety-grid">
              {livePortfolioMetrics(snapshot).map((metric) => (
                <div key={metric.id}>
                  <dt>{metric.label}</dt>
                  <dd>{metric.value}</dd>
                </div>
              ))}
            </dl>
            {snapshot.block_reasons.length ? (
              <ul className="live-safety-alerts">
                {snapshot.block_reasons.map((reason) => (
                  <li key={reason} data-severity={0}>
                    <strong>Live blocked</strong>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No active live block reasons reported.</p>
            )}
          </section>

          <div className="portfolio-grid">
            <section className="panel positions-panel">
              <h2>Broker positions</h2>
              {positions.length === 0 ? (
                <p className="muted">No broker positions reported in the current snapshot.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Qty</th>
                      <th>Side</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((row) => (
                      <tr key={row.id}>
                        <td>{row.symbol}</td>
                        <td>{row.quantity}</td>
                        <td>{row.detail ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="panel orders-panel">
              <h2>Open broker orders</h2>
              {orders.length === 0 ? (
                <p className="muted">No open broker orders reported.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Order</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((row) => (
                      <tr key={row.id}>
                        <td>{row.orderId}</td>
                        <td>{row.detail ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="panel risk-panel">
              <h2>Program caps</h2>
              <dl className="metric-list">
                {liveProgramCapMetrics(snapshot).map((metric) => (
                  <div key={metric.id}>
                    <dt>{metric.label}</dt>
                    <dd>{metric.value}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="panel data-health-panel">
              <h2>Reconciliation</h2>
              <dl className="metric-list">
                <div>
                  <dt>Health</dt>
                  <dd>{reconciliation?.reconciliation_health ?? snapshot.reconciliation_health}</dd>
                </div>
                <div>
                  <dt>Local open orders</dt>
                  <dd>{reconciliation?.local_open_orders.length ?? 0}</dd>
                </div>
                <div>
                  <dt>Ambiguous states</dt>
                  <dd>{ambiguous.length}</dd>
                </div>
                <div>
                  <dt>As of</dt>
                  <dd>{snapshot.as_of_ns ?? "—"}</dd>
                </div>
              </dl>
              {ambiguous.length ? (
                <ul>
                  {ambiguous.map((stateId) => (
                    <li key={stateId}>{stateId}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No ambiguous order states reported.</p>
              )}
            </section>
          </div>

          <p className="live-safety-hint">
            Reported broker state only. Execution controls remain unavailable in the Live workstation.
          </p>
        </>
      ) : null}
    </section>
  );
}
