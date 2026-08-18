import type { WorkspaceFuturesResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  futures: WorkspaceFuturesResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FuturesWorkspacePanel({
  instrumentId,
  futures,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading futures depth evidence…</div>;
  }

  if (!futures?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Futures / ES Depth</h2>
        <p>UNAVAILABLE — {futures?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Futures depth fixture is entitled for ES only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const snapshots = futures.snapshots ?? [];
  const latest = snapshots[snapshots.length - 1];

  return (
    <section className="futures-panel">
      <header className="panel-header">
        <h2>Futures / ES Depth</h2>
        <p>{futures.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:futures:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:futures:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>
          Research-only {futures.provenance ?? "fixture"} projection
          {futures.synthetic ? " (synthetic)" : ""}
        </span>
      </div>

      <dl className="metric-grid">
        <div>
          <dt>Contract month</dt>
          <dd>{futures.contract_month ?? latest?.contract_month ?? "—"}</dd>
        </div>
        <div>
          <dt>Exchange</dt>
          <dd>{futures.exchange ?? latest?.exchange ?? "CME"}</dd>
        </div>
        <div>
          <dt>Session</dt>
          <dd>{futures.session_state ?? latest?.session_state ?? "—"}</dd>
        </div>
        <div>
          <dt>Imbalance signal</dt>
          <dd>{futures.latest_imbalance_signal ?? latest?.imbalance_signal ?? "—"}</dd>
        </div>
        <div>
          <dt>Imbalance ratio</dt>
          <dd>{String(futures.latest_imbalance_ratio ?? latest?.imbalance_ratio ?? "—")}</dd>
        </div>
        <div>
          <dt>OFI</dt>
          <dd>{String(futures.latest_ofi_value ?? latest?.ofi_value ?? "—")}</dd>
        </div>
      </dl>

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
            <dt>RTH</dt>
            <dd>{latest.rth ? "Yes" : "No"}</dd>
          </div>
        </dl>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Best bid</th>
            <th>Best ask</th>
            <th>Imbalance</th>
            <th>Signal</th>
            <th>OFI</th>
            <th>Session</th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.best_bid}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.best_bid ?? "—"}</td>
              <td>{row.best_ask ?? "—"}</td>
              <td>{row.imbalance_ratio ?? "—"}</td>
              <td>{row.imbalance_signal ?? "—"}</td>
              <td>{row.ofi_value ?? "—"}</td>
              <td>{row.session_state ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
