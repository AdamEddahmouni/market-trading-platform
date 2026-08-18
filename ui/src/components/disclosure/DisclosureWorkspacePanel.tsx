import type { WorkspaceDisclosureResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  disclosure: WorkspaceDisclosureResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

export function DisclosureWorkspacePanel({
  instrumentId,
  disclosure,
  loading = false,
  onExplain,
  onInspect,
}: Props) {
  if (loading) {
    return <div className="app-loading">Loading disclosure evidence…</div>;
  }

  if (!disclosure?.available) {
    return (
      <aside className="capability-panel unavailable">
        <h2>Regulatory Disclosure</h2>
        <p>UNAVAILABLE — {disclosure?.reason ?? "WHALE_NO_ENTITLED_SOURCE"}</p>
        <p className="workspace-hint">
          SEC EDGAR disclosure fixture is entitled for BIYA within replay PIT cutoff.
        </p>
      </aside>
    );
  }

  const events = disclosure.events ?? [];

  return (
    <section className="disclosure-panel">
      <header className="panel-header">
        <h2>Regulatory Disclosure</h2>
        <p>{disclosure.disclaimer}</p>
        {disclosure.disclosure_lag_note ? <p className="workspace-hint">{disclosure.disclosure_lag_note}</p> : null}
        <div className="panel-actions">
          {onExplain ? (
            <button type="button" onClick={() => onExplain(`explain:disclosure:${instrumentId}`)}>
              Explain
            </button>
          ) : null}
          {onInspect ? (
            <button type="button" onClick={() => onInspect(`inspect:disclosure:${instrumentId}`)}>
              Inspect
            </button>
          ) : null}
        </div>
      </header>

      <div className="quality-banner">
        <span className="epistemic">OBSERVED</span>
        <span>DELAYED — SEC filings are not a live tape</span>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Accepted</th>
            <th>Form</th>
            <th>Filer</th>
            <th>Code</th>
            <th>Amendment</th>
          </tr>
        </thead>
        <tbody>
          {events.map((row) => (
            <tr key={`${row.accession_number}-${row.accepted_at}`}>
              <td>{row.accepted_at ?? "—"}</td>
              <td>{row.form_type ?? "—"}</td>
              <td>{row.filer ?? "—"}</td>
              <td>{row.transaction_code ?? "—"}</td>
              <td>{row.is_amendment ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
