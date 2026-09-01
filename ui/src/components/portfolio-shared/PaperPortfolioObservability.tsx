import type { PaperPortfolioResponse } from "../../api/client";

type Props = {
  data: PaperPortfolioResponse;
  onTraceOrder?: (intentId?: string, orderId?: string) => void;
  hideOrdersSection?: boolean;
};

export function PaperPortfolioObservability({ data, onTraceOrder, hideOrdersSection = false }: Props) {
  const { account, positions, orders, fills, risk, data_health, pnl, exposure } = data;

  return (
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
        {hideOrdersSection ? (
          <p className="muted">Operational order history is shown below.</p>
        ) : orders.length === 0 ? (
          <p className="muted">No orders submitted.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Side</th>
                <th>Qty</th>
                <th>State</th>
                <th>Filled</th>
                {onTraceOrder ? <th>Trace</th> : null}
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={String(order.order_id)}>
                  <td>{String(order.side ?? order.direction ?? "—")}</td>
                  <td>{String(order.quantity ?? order.filled_quantity ?? "—")}</td>
                  <td>{String(order.state)}</td>
                  <td>{String(order.filled_quantity ?? "—")}</td>
                  {onTraceOrder ? (
                    <td>
                      <button
                        type="button"
                        onClick={() =>
                          onTraceOrder(
                            typeof order.intent_id === "string" ? order.intent_id : undefined,
                            typeof order.order_id === "string" ? order.order_id : undefined,
                          )
                        }
                      >
                        Trace
                      </button>
                    </td>
                  ) : null}
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
  );
}
