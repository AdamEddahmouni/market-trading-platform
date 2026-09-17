import { Link } from "react-router-dom";
import { humanizeEnum, resolveSemanticState } from "../../state/semanticState";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { EmptyState, ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { StatePill } from "../imp-ui/StatePill";
import { LoadingState } from "../shared/LoadingState";
import { PageHeader } from "../shared/PageHeader";
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
  const ambiguous = reconciliation?.ambiguous_states ?? snapshot?.ambiguous_states ?? [];
  const reconHealth = reconciliation?.reconciliation_health ?? snapshot?.reconciliation_health;
  const recon = resolveSemanticState("portfolio", reconHealth);
  const brokerHealth = resolveSemanticState("providerHealth", snapshot?.broker_health);
  const liveBlocked = snapshot?.live_blocked;

  return (
    <section className="page portfolio-page live-portfolio-page">
      <PageHeader
        eyebrow="Live · broker-observed read-only"
        title="Live Portfolio"
        subtitle="Broker-reported positions and open orders for operational safety review. This view never exposes execution controls and is not a Paper P&L account."
        actions={
          <Link className="portfolio-row-action" to="/live-canary">
            Open live canary
          </Link>
        }
      />

      <AttentionBanner
        tone="caution"
        affects="Positions and orders here are observational broker reports, not simulated Paper P&L."
      >
        Live Portfolio is observational. IMP does not place live broker orders from this surface.
      </AttentionBanner>

      {state === "loading" ? <LoadingState label="Loading broker portfolio snapshot…" /> : null}
      {state === "error" ? (
        <ErrorState
          title="Broker portfolio snapshot unavailable."
          affects="Live positions, orders, and reconciliation cannot be shown."
        />
      ) : null}

      {state === "ready" && snapshot ? (
        <>
          {liveBlocked && snapshot.block_reasons.length ? (
            <div className="portfolio-attention-stack">
              {snapshot.block_reasons.map((reason) => (
                <AttentionBanner
                  key={reason}
                  tone="critical"
                  affects="Live execution remains blocked. This page stays read-only."
                  action={{ label: "Open live canary", href: "/live-canary" }}
                >
                  Live blocked: {humanizeEnum(reason)}
                </AttentionBanner>
              ))}
            </div>
          ) : (
            <p className="muted">No active live block reasons reported.</p>
          )}

          <section className="panel portfolio-section" aria-labelledby="live-account-heading">
            <h2 id="live-account-heading">Account</h2>
            <dl className="portfolio-fact-grid">
              {livePortfolioMetrics(snapshot).map((metric) => (
                <div key={metric.id}>
                  <dt>{metric.label}</dt>
                  <dd>
                    {metric.id === "fingerprint" && snapshot.account_fingerprint ? (
                      <CopyableIdentifier value={snapshot.account_fingerprint} />
                    ) : metric.id === "broker-health" ? (
                      <StatePill
                        tone={brokerHealth.tone}
                        label={brokerHealth.label}
                        raw={snapshot.broker_health}
                        size="sm"
                      />
                    ) : metric.id === "reconciliation" ? (
                      <StatePill tone={recon.tone} label={recon.label} raw={reconHealth} size="sm" />
                    ) : (
                      humanizeEnum(metric.value)
                    )}
                  </dd>
                </div>
              ))}
            </dl>
            {snapshot.as_of_ns ? (
              <FreshnessIndicator backendLabel={undefined} asOf={snapshot.as_of_ns} decays />
            ) : null}
          </section>

          <div className="portfolio-grid">
            <section className="panel portfolio-section" aria-labelledby="live-positions-heading">
              <h2 id="live-positions-heading">Broker positions</h2>
              {positions.length === 0 ? (
                <EmptyState
                  title="No broker positions"
                  reason="The current canary snapshot reports no live positions."
                />
              ) : (
                <>
                  <div className="portfolio-table-wrap portfolio-positions-table-wrap">
                    <table className="data-table">
                      <caption className="visually-hidden imp-visually-hidden">
                        Broker-reported positions
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Symbol</th>
                          <th scope="col">Qty</th>
                          <th scope="col">Side</th>
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
                  </div>
                  <ul className="portfolio-position-cards">
                    {positions.map((row) => (
                      <li key={row.id} className="portfolio-position-card">
                        <header>
                          <h3>{row.symbol}</h3>
                          <p>
                            {row.detail ?? "Side unavailable"} · {row.quantity}
                          </p>
                        </header>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            <section className="panel portfolio-section" aria-labelledby="live-orders-heading">
              <h2 id="live-orders-heading">Open broker orders</h2>
              {orders.length === 0 ? (
                <EmptyState
                  title="No open broker orders"
                  reason="The current canary snapshot reports no open broker orders."
                />
              ) : (
                <div className="portfolio-table-wrap">
                  <table className="data-table">
                    <caption className="visually-hidden imp-visually-hidden">
                      Broker-reported open orders
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Order</th>
                        <th scope="col">Detail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((row) => (
                        <tr key={row.id}>
                          <td>
                            <CopyableIdentifier value={row.orderId} chars={6} />
                          </td>
                          <td>{row.detail ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="panel portfolio-section" aria-labelledby="live-caps-heading">
              <h2 id="live-caps-heading">Program caps</h2>
              <dl className="portfolio-metric-strip">
                {liveProgramCapMetrics(snapshot).map((metric) => (
                  <div key={metric.id}>
                    <dt>{metric.label}</dt>
                    <dd>{metric.value}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="panel portfolio-section" aria-labelledby="live-recon-heading">
              <h2 id="live-recon-heading">Reconciliation</h2>
              <dl className="portfolio-metric-strip">
                <div>
                  <dt>Health</dt>
                  <dd>
                    <StatePill tone={recon.tone} label={recon.label} raw={reconHealth} size="sm" />
                  </dd>
                </div>
                <div>
                  <dt>Local open orders</dt>
                  <dd>{reconciliation?.local_open_orders.length ?? 0}</dd>
                </div>
                <div>
                  <dt>Ambiguous states</dt>
                  <dd>{ambiguous.length}</dd>
                </div>
              </dl>
              {ambiguous.length ? (
                <ul>
                  {ambiguous.map((stateId) => (
                    <li key={stateId}>
                      <CopyableIdentifier value={stateId} />
                    </li>
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
