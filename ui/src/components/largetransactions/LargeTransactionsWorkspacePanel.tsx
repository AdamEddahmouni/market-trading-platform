import type { WorkspaceLargeTransactionsResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  largeTransactions: WorkspaceLargeTransactionsResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function LargeTransactionsWorkspacePanel({
  instrumentId,
  largeTransactions,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading large-transaction evidence…</div>;
  }

  if (!largeTransactions?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Large Transactions</h2>
        <p>UNAVAILABLE — {largeTransactions?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Large-print fixture is entitled for NVDA only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const prints = largeTransactions.prints ?? [];

  return (
    <section className="large-transactions-panel">
      <header className="panel-header">
        <h2>Large Transactions</h2>
        <p>{largeTransactions.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button
              type="button"
              onClick={() => onExplain(`explain:large-transactions:${instrumentId}`)}
            >
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button
              type="button"
              onClick={() => onInspect(`inspect:large-transactions:${instrumentId}`)}
            >
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only fixture projection — size normalized to rolling volume</span>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Size</th>
            <th>Price</th>
            <th>Side</th>
            <th>Size ratio</th>
            <th>Threshold</th>
            <th>Direction</th>
          </tr>
        </thead>
        <tbody>
          {prints.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.print_size}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.print_size ?? "—"}</td>
              <td>{row.price ?? "—"}</td>
              <td>{row.side ?? "—"}</td>
              <td>{row.size_ratio ?? "—"}</td>
              <td>{row.threshold_gate_ok ? "PASS" : "FAIL"}</td>
              <td>{row.direction_label ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
