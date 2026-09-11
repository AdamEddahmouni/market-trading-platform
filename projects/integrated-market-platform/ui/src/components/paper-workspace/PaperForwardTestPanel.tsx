import { buildForwardTestPanelModel, formatForwardTestState, type ForwardTestRecord } from "./buildForwardTestPanelModel";

type Props = {
  records: ForwardTestRecord[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
};

export function PaperForwardTestPanel({ records, isLoading, isError, errorMessage }: Props) {
  const model = buildForwardTestPanelModel(records);

  if (isLoading) {
    return (
      <section className="panel paper-forward-test-panel" aria-labelledby="paper-forward-test-heading">
        <header>
          <h2 id="paper-forward-test-heading">{model.label}</h2>
          <span className="paper-forward-test-mode-badge">{model.modeLabel}</span>
        </header>
        <p role="status">Loading forward-test state…</p>
      </section>
    );
  }

  if (isError) {
    return (
      <section className="panel paper-forward-test-panel" aria-labelledby="paper-forward-test-heading">
        <header>
          <h2 id="paper-forward-test-heading">{model.label}</h2>
          <span className="paper-forward-test-mode-badge">{model.modeLabel}</span>
        </header>
        <p className="paper-cockpit-warning" role="alert">
          {errorMessage ?? "Forward-test request failed."}
        </p>
      </section>
    );
  }

  return (
    <section className="panel paper-forward-test-panel" aria-labelledby="paper-forward-test-heading">
      <header>
        <h2 id="paper-forward-test-heading">{model.label}</h2>
        <span className="paper-forward-test-mode-badge">{model.modeLabel}</span>
      </header>

      {!model.hasRecords ? <p className="muted">{model.emptyMessage}</p> : null}

      {model.hasRecords ? (
        <>
          <dl className="paper-forward-test-summary">
            <div>
              <dt>Pending</dt>
              <dd>{model.pendingCount}</dd>
            </div>
            <div>
              <dt>Evaluated</dt>
              <dd>{model.evaluatedCount}</dd>
            </div>
            <div>
              <dt>Rejected / invalid</dt>
              <dd>{model.rejectedCount}</dd>
            </div>
          </dl>

          <ul className="paper-forward-test-list">
            {model.records.map((record) => (
              <li key={record.forward_test_id} className={`paper-forward-test-item state-${record.state}`}>
                <div className="paper-forward-test-item-header">
                  <strong>{record.symbol}</strong>
                  <span className="paper-forward-test-state">{formatForwardTestState(record.state)}</span>
                </div>
                <p className="muted">
                  {record.direction} · {record.strategy_id}@{record.strategy_version}
                </p>
                {record.paper_order_id ? (
                  <p className="muted">Paper order: {record.paper_order_id}</p>
                ) : null}
                {record.signal_outcome?.directional_correct != null ? (
                  <p>
                    Directional correctness:{" "}
                    {record.signal_outcome.directional_correct ? "correct" : "incorrect"}
                  </p>
                ) : null}
                {record.failure_reason ? (
                  <p className="paper-cockpit-warning">{record.failure_reason}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
