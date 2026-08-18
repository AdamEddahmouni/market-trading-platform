import type { WorkspaceOrderBookResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  orderBook: WorkspaceOrderBookResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OrderBookWorkspacePanel({
  instrumentId,
  orderBook,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading order-book evidence…</div>;
  }

  if (!orderBook?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Order Book / Depth</h2>
        <p>UNAVAILABLE — {orderBook?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Order-book fixture is entitled for NVDA only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const snapshots = orderBook.snapshots ?? [];
  const latest = snapshots[snapshots.length - 1];

  return (
    <section className="order-book-panel">
      <header className="panel-header">
        <h2>Order Book / Depth</h2>
        <p>{orderBook.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:order-book:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:order-book:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only fixture projection — snapshot provenance retained</span>
      </div>

      {latest ? (
        <dl className="metric-grid">
          <div>
            <dt>Best bid</dt>
            <dd>{String(latest.best_bid)}</dd>
          </div>
          <div>
            <dt>Best ask</dt>
            <dd>{String(latest.best_ask)}</dd>
          </div>
          <div>
            <dt>Imbalance ratio</dt>
            <dd>{String(latest.imbalance_ratio)}</dd>
          </div>
          <div>
            <dt>OFI</dt>
            <dd>{String(latest.ofi_value)}</dd>
          </div>
          <div>
            <dt>Direction</dt>
            <dd>{String(latest.direction_label)}</dd>
          </div>
          <div>
            <dt>Levels</dt>
            <dd>{String(latest.level_count)}</dd>
          </div>
        </dl>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Best bid</th>
            <th>Bid size</th>
            <th>Best ask</th>
            <th>Ask size</th>
            <th>Imbalance</th>
            <th>OFI</th>
            <th>Direction</th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.best_bid}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.best_bid ?? "—"}</td>
              <td>{row.bid_size ?? "—"}</td>
              <td>{row.best_ask ?? "—"}</td>
              <td>{row.ask_size ?? "—"}</td>
              <td>{row.imbalance_ratio ?? "—"}</td>
              <td>{row.ofi_value ?? "—"}</td>
              <td>{row.direction_label ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
