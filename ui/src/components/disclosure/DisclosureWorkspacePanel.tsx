import type { WorkspaceDisclosureResponse } from "../../api/schemas";

type Props = {
  instrumentId: string;
  disclosure: WorkspaceDisclosureResponse | null;
  loading?: boolean;
  onExplain?: (ref: string) => void;
  onInspect?: (ref: string) => void;
};

function formatParticipantSummary(summary: WorkspaceDisclosureResponse["participant_summary"]) {
  if (!summary) {
    return null;
  }
  const parts: string[] = [];
  if (summary.discretionary_buy_count) {
    parts.push(`${summary.discretionary_buy_count} discretionary insider buy(s)`);
  }
  if (summary.activist_disclosure_count) {
    parts.push(`${summary.activist_disclosure_count} activist disclosure(s)`);
  }
  if (summary.compensation_count) {
    parts.push(`${summary.compensation_count} compensation/non-directional`);
  }
  if (summary.open_market_sell_count) {
    parts.push(`${summary.open_market_sell_count} open-market sell(s)`);
  }
  if (summary.institutional_snapshot_count) {
    parts.push(`${summary.institutional_snapshot_count} institutional snapshot(s)`);
  }
  if (parts.length === 0 && summary.action_count) {
    parts.push(`${summary.action_count} participant action(s)`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

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
  const participantSummary = formatParticipantSummary(disclosure.participant_summary);
  const participantEvidence = disclosure.participant_evidence ?? [];

  return (
    <section className="disclosure-panel">
      <header className="panel-header">
        <h2>Regulatory Disclosure</h2>
        <p>{disclosure.disclaimer}</p>
        {disclosure.disclosure_lag_note ? <p className="workspace-hint">{disclosure.disclosure_lag_note}</p> : null}
        {participantSummary ? (
          <p className="workspace-hint">
            Participant semantics: {participantSummary}
            {disclosure.participant_summary?.direction
              ? ` (direction=${disclosure.participant_summary.direction})`
              : ""}
          </p>
        ) : null}
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

      {participantEvidence.length > 0 ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Participant</th>
              <th>Semantics</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {participantEvidence.map((row) => (
              <tr key={`${row.payload_type}-${row.display_name}-${row.action_type}`}>
                <td>{row.payload_type ?? "—"}</td>
                <td>{row.display_name ?? "—"}</td>
                <td>
                  {row.action_type ?? "—"}
                  {row.insider_discretion ? ` / ${row.insider_discretion}` : ""}
                  {row.stake_percent != null ? ` / stake ${row.stake_percent}%` : ""}
                  {row.campaign_objective ? ` / ${row.campaign_objective}` : ""}
                </td>
                <td>{row.cross_lane_signal ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Accepted</th>
            <th>Form</th>
            <th>Filer</th>
            <th>Code</th>
            <th>Shares</th>
            <th>Price</th>
            <th>Stake %</th>
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
              <td>{row.shares ?? "—"}</td>
              <td>{row.price_per_share ?? "—"}</td>
              <td>{row.stake_percent ?? "—"}</td>
              <td>{row.is_amendment ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
