import { usePaperTraceQuery } from "../../api/hooks";

type ExecutionTracePanelProps = {
  intentId?: string;
  orderId?: string;
  onClose: () => void;
};

export function ExecutionTracePanel({ intentId, orderId, onClose }: ExecutionTracePanelProps) {
  const traceQuery = usePaperTraceQuery({ intentId, orderId }, Boolean(intentId || orderId));

  return (
    <aside className="execution-trace-panel">
      <header>
        <h3>Execution trace</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </header>
      {traceQuery.isLoading ? <p className="muted">Loading trace…</p> : null}
      {traceQuery.isError ? <p className="order-ticket-error">Trace unavailable.</p> : null}
      {traceQuery.data ? (
        <div className="trace-steps">
          <dl className="metric-list">
            <div>
              <dt>Market data provider</dt>
              <dd>{String(traceQuery.data.trace.market_data_provider ?? "—")}</dd>
            </div>
            <div>
              <dt>Execution provider</dt>
              <dd>{String(traceQuery.data.trace.execution_provider ?? "INTERNAL")}</dd>
            </div>
            <div>
              <dt>Execution mode</dt>
              <dd>{String(traceQuery.data.trace.execution_mode ?? "—")}</dd>
            </div>
            <div>
              <dt>Authority</dt>
              <dd>{String(traceQuery.data.trace.execution_authority ?? "—")}</dd>
            </div>
            <div>
              <dt>Broker order submitted</dt>
              <dd>{traceQuery.data.trace.broker_order_submitted ? "YES" : "NO"}</dd>
            </div>
            <div>
              <dt>Broker order ID</dt>
              <dd>{String(traceQuery.data.trace.broker_order_id ?? "NONE")}</dd>
            </div>
          </dl>
          {traceQuery.data.trace.steps.map((step, index) => (
            <details key={`${step.stage}-${step.sequence}`} className="trace-step" open={index === 0}>
              <summary>
                {step.stage}: {step.summary}
              </summary>
              {step.metadata ? (
                <pre>{JSON.stringify(step.metadata, null, 2)}</pre>
              ) : null}
            </details>
          ))}
        </div>
      ) : null}
    </aside>
  );
}
