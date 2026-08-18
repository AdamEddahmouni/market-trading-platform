import { Link } from "react-router-dom";
import type { WorkspaceOrderFlowResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  orderFlow: WorkspaceOrderFlowResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderFlowWorkspacePanel({
  instrumentId,
  orderFlow,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading order-flow evidence…</div>;
  }

  if (!orderFlow?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Order Flow / CVD</h2>
        <p>UNAVAILABLE — {orderFlow?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Order-flow fixture is entitled for NVDA only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const bars = orderFlow.bars ?? [];
  const lastBar = bars[bars.length - 1];

  return (
    <section className="order-flow-panel">
      <header className="panel-header">
        <h2>Order Flow / CVD</h2>
        <p>{orderFlow.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:order-flow:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:order-flow:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only fixture projection</span>
      </div>

      {lastBar ? (
        <dl className="metric-grid">
          <div>
            <dt>Cumulative delta</dt>
            <dd>{String(lastBar.cumulative_delta)}</dd>
          </div>
          <div>
            <dt>Last bar delta</dt>
            <dd>{String(lastBar.delta)}</dd>
          </div>
          <div>
            <dt>Aggressor provenance</dt>
            <dd>{String(lastBar.aggressor_provenance)}</dd>
          </div>
          <div>
            <dt>Quality</dt>
            <dd>{String(lastBar.quality)}</dd>
          </div>
        </dl>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Bar time</th>
            <th>Delta</th>
            <th>CVD</th>
            <th>Volume</th>
            <th>Quality</th>
            <th>Provenance</th>
          </tr>
        </thead>
        <tbody>
          {bars.map((bar) => (
            <tr key={`${bar.bar_time}-${bar.normalized_event_id}`}>
              <td>{bar.bar_time}</td>
              <td>{String(bar.delta)}</td>
              <td>{String(bar.cumulative_delta)}</td>
              <td>{String(bar.volume)}</td>
              <td>{String(bar.quality)}</td>
              <td>{String(bar.aggressor_provenance)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <aside className="capability-panel">
        <h3>Depth / DOM</h3>
        <p>
          Order-book depth is available on the dedicated{" "}
          <Link to={`/workspace/${instrumentId}/order-book`}>Order Book workspace</Link>.
        </p>
      </aside>
    </section>
  );
}
