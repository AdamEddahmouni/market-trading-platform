import type { WorkspaceCatalystResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  catalyst: WorkspaceCatalystResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function CatalystWorkspacePanel({
  instrumentId,
  catalyst,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading catalyst evidence…</div>;
  }

  if (!catalyst?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Public Catalyst</h2>
        <p>UNAVAILABLE — {catalyst?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          Catalyst fixture is entitled for BOXL only within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const rows = catalyst.catalysts ?? [];

  return (
    <section className="catalyst-panel">
      <header className="panel-header">
        <h2>Public Catalyst</h2>
        <p>{catalyst.disclaimer}</p>
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:catalyst:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:catalyst:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">INFERRED</span>
        <span>Research-only fixture projection</span>
      </div>

      <dl className="metric-grid">
        <div>
          <dt>Latest headline</dt>
          <dd>{catalyst.latest_headline ?? "—"}</dd>
        </div>
        <div>
          <dt>Latest lean</dt>
          <dd>{catalyst.latest_lean ?? "—"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{String(catalyst.latest_confidence ?? "—")}</dd>
        </div>
        <div>
          <dt>Gate</dt>
          <dd>{catalyst.latest_gate_ok ? "PASS" : "FAIL"}</dd>
        </div>
      </dl>

      <table className="data-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th>Headline</th>
            <th>Lean</th>
            <th>Confidence</th>
            <th>Gate</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.normalized_event_id ?? `${row.event_time}-${row.headline}`}>
              <td>{row.event_time ?? "—"}</td>
              <td>{row.catalyst_type ?? "—"}</td>
              <td>{row.headline ?? "—"}</td>
              <td>{row.lean ?? "—"}</td>
              <td>{row.confidence ?? "—"}</td>
              <td>{row.gate_ok ? "PASS" : "FAIL"}</td>
              <td>{row.source ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
