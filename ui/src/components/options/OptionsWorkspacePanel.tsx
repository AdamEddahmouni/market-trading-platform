import type { WorkspaceOptionsResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  options: WorkspaceOptionsResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function OptionsWorkspacePanel({
  instrumentId,
  options,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading options evidence…</div>;
  }

  if (!options?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Options / Unusual Activity</h2>
        <p>UNAVAILABLE — {options?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Options fixture is entitled for BIYA only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const activities = options.activities ?? [];

  return (
    <section className="options-panel">
      <header className="panel-header">
        <h2>Options / Unusual Activity</h2>
        <p>{options.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:options:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:options:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">DERIVED</span>
        <span>Research-only fixture projection — direction may remain ambiguous</span>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Event time</th>
            <th>Type</th>
            <th>Strike</th>
            <th>Expiry</th>
            <th>Volume</th>
            <th>OI</th>
            <th>Vol/OI</th>
            <th>Liquidity</th>
            <th>Direction</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {activities.map((row) => (
            <tr key={`${row.event_time}-${row.normalized_event_id}`}>
              <td>{row.event_time}</td>
              <td>{row.option_type}</td>
              <td>{String(row.strike)}</td>
              <td>{row.expiry}</td>
              <td>{String(row.volume)}</td>
              <td>{String(row.open_interest)}</td>
              <td>{String(row.volume_oi_ratio)}</td>
              <td>{row.liquidity_ok ? "PASS" : "FAIL"}</td>
              <td>{row.direction_label}</td>
              <td>{String(row.confirmation_score)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <aside className="capability-panel unavailable">
        <h3>Full Options Chain</h3>
        <p>UNAVAILABLE — options.chain capability not entitled.</p>
      </aside>
    </section>
  );
}
