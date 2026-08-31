import { useEffect, useState } from "react";
import {
  useClosePaperSessionMutation,
  useOpenPaperSessionMutation,
  usePaperPortfolioQuery,
} from "../api/hooks";
import { ExecutionTracePanel } from "./paper/ExecutionTracePanel";
import { OrderTicket } from "./paper/OrderTicket";
import { canUsePaperActions } from "./mode-session/modeAuthority";
import type { Mode } from "./mode-session/types";

type StoredSession = {
  session_id: string;
  status: string;
  created_at?: number;
  closed_at?: number | null;
  data_mode?: string;
  execution_mode?: string;
};

type Props = {
  mode: Mode;
  paperActionsPermitted: boolean;
};

export function PortfolioPage({ mode, paperActionsPermitted }: Props) {
  const portfolioQuery = usePaperPortfolioQuery();
  const openSession = useOpenPaperSessionMutation();
  const closeSession = useClosePaperSessionMutation();
  const [traceIntentId, setTraceIntentId] = useState<string | undefined>();
  const [traceOrderId, setTraceOrderId] = useState<string | undefined>();
  const [sessions, setSessions] = useState<StoredSession[]>([]);

  useEffect(() => {
    void fetch("/paper/sessions")
      .then((response) => response.json())
      .then((payload) => setSessions(payload.sessions ?? []))
      .catch(() => undefined);
  }, [portfolioQuery.data?.session?.session_id, portfolioQuery.data?.account?.session_id]);

  if (portfolioQuery.isLoading) {
    return (
      <section className="page portfolio-page">
        <h1>PORTFOLIO</h1>
        <p className="muted">Loading account observability…</p>
      </section>
    );
  }

  if (portfolioQuery.isError || !portfolioQuery.data) {
    return (
      <section className="page portfolio-page">
        <h1>PORTFOLIO</h1>
        <div className="capability-panel unavailable">
          <p>Account observability unavailable.</p>
        </div>
      </section>
    );
  }

  const data = portfolioQuery.data;
  const { account, positions, orders, fills, risk, data_health, session, pnl, exposure } = data;
  const symbol = data.active_instrument ?? null;
  const actionEligible = canUsePaperActions(mode, paperActionsPermitted, account);

  return (
    <section className="page portfolio-page">
      <header className="portfolio-header">
        <h1>PORTFOLIO</h1>
        <p className="portfolio-provenance">
          DATA: {account.data_mode.replace(/_/g, " ")} · {account.data_provider} · QUALITY{" "}
          {data_health.state}
          {" · "}
          EXEC: {account.execution_mode.replace(/_/g, " ")} · AUTH {account.execution_authority}
        </p>
        {session ? (
          <p className="muted">
            Session {session.session_id.slice(0, 12)}… · cash starting{" "}
            {session.starting_cash_minor ? `${session.starting_cash_minor} minor` : "UNAVAILABLE"}
          </p>
        ) : null}
        {actionEligible ? (
          <div className="live-actions">
            <button
              type="button"
              onClick={() => void closeSession.mutateAsync()}
              disabled={closeSession.isPending}
            >
              Archive session
            </button>
            <button
              type="button"
              onClick={() => void openSession.mutateAsync(symbol ?? undefined)}
              disabled={openSession.isPending}
            >
              New Paper Session
            </button>
          </div>
        ) : null}
      </header>

      <div className="portfolio-layout">
        <div className="portfolio-main">
          {actionEligible ? (
            <OrderTicket
              symbol={symbol}
              executionAuthority={account.execution_authority}
              executionMode={account.execution_mode}
              dataMode={account.data_mode}
              maxOrderShares={risk.limits.max_order_shares}
              onSubmitted={(intentId) => {
                if (intentId) setTraceIntentId(intentId);
              }}
            />
          ) : (
            <aside className="panel mode-restriction-note" role="note">
              <strong>{mode} is read-only here.</strong>
              <p>Order and paper-session controls are unavailable for this context.</p>
            </aside>
          )}

          <div className="portfolio-grid">
            <section className="panel account-panel">
              <h2>Account</h2>
              <dl className="metric-list">
                <div>
                  <dt>Cash</dt>
                  <dd>{account.cash_display}</dd>
                </div>
                <div>
                  <dt>Buying power</dt>
                  <dd>{account.cash_display}</dd>
                </div>
                <div>
                  <dt>Realized P&amp;L</dt>
                  <dd>{account.realized_pnl_display}</dd>
                </div>
                <div>
                  <dt>Execution provider</dt>
                  <dd>{account.execution_provider}</dd>
                </div>
              </dl>
            </section>

            <section className="panel pnl-panel">
              <h2>P&amp;L</h2>
              <dl className="metric-list">
                <div>
                  <dt>Realized</dt>
                  <dd>{pnl?.realized_display ?? account.realized_pnl_display}</dd>
                </div>
                <div>
                  <dt>Unrealized</dt>
                  <dd>{pnl?.unrealized_display ?? "—"}</dd>
                </div>
                <div>
                  <dt>Total</dt>
                  <dd>{pnl?.total_display ?? account.realized_pnl_display}</dd>
                </div>
              </dl>
            </section>

            <section className="panel exposure-panel">
              <h2>Exposure</h2>
              <dl className="metric-list">
                <div>
                  <dt>Gross</dt>
                  <dd>{exposure?.gross_shares ?? 0} sh</dd>
                </div>
                <div>
                  <dt>Net</dt>
                  <dd>{exposure?.net_shares ?? 0} sh</dd>
                </div>
              </dl>
            </section>

            <section className="panel risk-panel">
              <h2>Risk</h2>
              <dl className="metric-list">
                <div>
                  <dt>Kill switch</dt>
                  <dd>{risk.kill_switch_active ? "ACTIVE" : "OFF"}</dd>
                </div>
                <div>
                  <dt>Open orders</dt>
                  <dd>{risk.open_order_count}</dd>
                </div>
                <div>
                  <dt>Last decision</dt>
                  <dd>
                    {risk.last_decision && typeof risk.last_decision.decision === "string"
                      ? risk.last_decision.decision
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Max order</dt>
                  <dd>{risk.limits.max_order_shares} sh</dd>
                </div>
                <div>
                  <dt>Max position</dt>
                  <dd>{risk.limits.max_position_shares} sh</dd>
                </div>
              </dl>
            </section>

            <section className="panel positions-panel">
              <h2>Positions</h2>
              {positions.length === 0 ? (
                <p className="muted">No open positions.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Qty</th>
                      <th>Avg fill</th>
                      <th>Mark</th>
                      <th>Mark quality</th>
                      <th>Mark as of</th>
                      <th>Unrealized</th>
                      <th>Mark provider</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((row) => (
                      <tr key={row.instrument_id}>
                        <td>{row.symbol}</td>
                        <td>{row.quantity}</td>
                        <td>{row.average_fill_display ?? "—"}</td>
                        <td>{row.mark_display ?? "—"}</td>
                        <td>{row.mark_quality ?? "—"}</td>
                        <td>{row.mark_as_of_ns ?? "—"}</td>
                        <td>{row.unrealized_pnl_display ?? "—"}</td>
                        <td>{row.mark_provider ?? row.mark_source ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="panel orders-panel">
              <h2>Orders</h2>
              {orders.length === 0 ? (
                <p className="muted">No orders submitted.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Side</th>
                      <th>Qty</th>
                      <th>State</th>
                      <th>Filled</th>
                      <th>Trace</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={String(order.order_id)}>
                        <td>{String(order.side ?? order.direction ?? "—")}</td>
                        <td>{String(order.quantity ?? order.filled_quantity ?? "—")}</td>
                        <td>{String(order.state)}</td>
                        <td>{String(order.filled_quantity ?? "—")}</td>
                        <td>
                          <button
                            type="button"
                            onClick={() => {
                              setTraceIntentId(
                                typeof order.intent_id === "string" ? order.intent_id : undefined,
                              );
                              setTraceOrderId(typeof order.order_id === "string" ? order.order_id : undefined);
                            }}
                          >
                            Trace
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="panel fills-panel">
              <h2>Fills</h2>
              {fills.length === 0 ? (
                <p className="muted">No fills recorded.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Side</th>
                      <th>Qty</th>
                      <th>Price (minor)</th>
                      <th>Order</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fills.map((fill) => (
                      <tr key={String(fill.fill_id)}>
                        <td>{String(fill.direction)}</td>
                        <td>{String(fill.fill_quantity)}</td>
                        <td>{String(fill.fill_price_minor)}</td>
                        <td>{String(fill.order_id).slice(0, 8)}…</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="panel session-history-panel">
              <h2>Session history</h2>
              {sessions.length === 0 ? (
                <p className="muted">No persisted sessions yet.</p>
              ) : (
                <ul>
                  {sessions.map((row) => (
                    <li key={row.session_id}>
                      {row.status} · {row.session_id.slice(0, 12)}… · {row.data_mode} / {row.execution_mode}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="panel data-health-panel">
              <h2>Data / execution health</h2>
              <dl className="metric-list">
                <div>
                  <dt>Data quality</dt>
                  <dd>{data_health.state}</dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>{data_health.simulation_model ?? "UNAVAILABLE"}</dd>
                </div>
              </dl>
              <p className="muted">{data_health.detail}</p>
            </section>
          </div>
        </div>

        {traceIntentId || traceOrderId ? (
          <ExecutionTracePanel
            intentId={traceIntentId}
            orderId={traceOrderId}
            onClose={() => {
              setTraceIntentId(undefined);
              setTraceOrderId(undefined);
            }}
          />
        ) : null}
      </div>
    </section>
  );
}
