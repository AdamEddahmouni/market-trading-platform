import type { WorkspaceFundEtfResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  fundEtf: WorkspaceFundEtfResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function FundEtfWorkspacePanel({
  instrumentId,
  fundEtf,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading fund/ETF context evidence…</div>;
  }

  if (!fundEtf?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Fund / ETF Cross-Asset</h2>
        <p>UNAVAILABLE — {fundEtf?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Fund/ETF fixture is entitled for NVDA only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const rows = fundEtf.events ?? [];

  return (
    <section className="fund-etf-panel">
      <header className="panel-header">
        <h2>Fund / ETF Cross-Asset</h2>
        <p>{fundEtf.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:fund-etf:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:fund-etf:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only synthetic flow proxy projection</span>
      </div>

      <dl className="metric-grid">
        <div>
          <dt>Regime</dt>
          <dd>{fundEtf.latest_regime_label ?? "—"}</dd>
        </div>
        <div>
          <dt>Flow proxy ratio</dt>
          <dd>{String(fundEtf.latest_flow_proxy_ratio ?? "—")}</dd>
        </div>
        <div>
          <dt>Correlation (20d)</dt>
          <dd>{String(fundEtf.latest_correlation_20d ?? "—")}</dd>
        </div>
      </dl>

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th>ETF</th>
            <th>Flow</th>
            <th>Ratio</th>
            <th>Regime</th>
            <th>Correlation</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.etf_ticker}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.event_type ?? "—"}</td>
              <td>{row.etf_ticker ?? "—"}</td>
              <td>{row.flow_direction ?? "—"}</td>
              <td>{row.flow_proxy_ratio ?? "—"}</td>
              <td>{row.regime_label ?? "—"}</td>
              <td>{row.correlation_20d ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
