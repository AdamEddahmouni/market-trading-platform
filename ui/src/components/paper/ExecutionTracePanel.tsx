import { usePaperTraceQuery } from "../../api/hooks";
import { PaperPersistedSourceContextPanel } from "../paper-portfolio/PaperPersistedSourceContextPanel";
import { parsePersistedPaperDecisionProvenance } from "../paper-portfolio/paperDecisionProvenance";
import { JsonDetailPanel } from "../shared/JsonDetailPanel";
import { LoadingState } from "../shared/LoadingState";

type ExecutionTracePanelProps = {
  intentId?: string;
  orderId?: string;
  onClose: () => void;
};

function traceDecisionCorrelation(trace: { steps: Array<{ metadata?: Record<string, unknown> }> }): string | null {
  for (const step of trace.steps) {
    const metadata = step.metadata;
    if (!metadata) continue;
    const intent = metadata.intent;
    if (intent && typeof intent === "object" && !Array.isArray(intent)) {
      const correlationId = (intent as Record<string, unknown>).correlation_id;
      if (typeof correlationId === "string" && correlationId.trim()) return correlationId.trim();
    }
    const direct = metadata.correlation_id;
    if (typeof direct === "string" && direct.trim()) return direct.trim();
  }
  return null;
}

function traceClientOrderId(trace: { steps: Array<{ metadata?: Record<string, unknown> }> }): string | null {
  for (const step of trace.steps) {
    const metadata = step.metadata;
    if (!metadata) continue;
    const intent = metadata.intent;
    if (intent && typeof intent === "object" && !Array.isArray(intent)) {
      const clientOrderId = (intent as Record<string, unknown>).client_order_id;
      if (typeof clientOrderId === "string" && clientOrderId.trim()) return clientOrderId.trim();
    }
    const direct = metadata.client_order_id;
    if (typeof direct === "string" && direct.trim()) return direct.trim();
  }
  return null;
}

function traceProvenanceLabel(correlationId: string | null, clientOrderId: string | null): string | null {
  if (!correlationId) return null;
  const provenance = parsePersistedPaperDecisionProvenance(correlationId, clientOrderId);
  if (!provenance.isDecisionProvenance) return null;
  return provenance.provenanceLabel;
}

function traceDecisionSourceSnapshot(
  trace: { steps: Array<{ metadata?: Record<string, unknown> }> },
): unknown {
  for (const step of trace.steps) {
    const metadata = step.metadata;
    if (!metadata) continue;
    const nestedIntent = metadata.intent;
    if (nestedIntent && typeof nestedIntent === "object" && !Array.isArray(nestedIntent)) {
      const snapshot = (nestedIntent as Record<string, unknown>).decision_source_snapshot;
      if (snapshot) return snapshot;
    }
    if (metadata.decision_source_snapshot) return metadata.decision_source_snapshot;
  }
  return null;
}

function tracePersistedSourceContext(
  trace: { steps: Array<{ metadata?: Record<string, unknown> }> },
  correlationId: string | null,
  clientOrderId: string | null,
) {
  const snapshot = traceDecisionSourceSnapshot(trace);
  return parsePersistedPaperDecisionProvenance(
    correlationId,
    clientOrderId,
    null,
    snapshot,
  ).persistedSourceContext;
}

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
      {traceQuery.isLoading ? <LoadingState label="Loading trace…" /> : null}
      {traceQuery.isError ? <p className="order-ticket-error">Trace unavailable.</p> : null}
      {traceQuery.data ? (
        <div className="trace-steps">
          <dl className="metric-list">
            {(() => {
              const correlationId = traceDecisionCorrelation(traceQuery.data.trace);
              const clientOrderId = traceClientOrderId(traceQuery.data.trace);
              const provenanceLabel = traceProvenanceLabel(correlationId, clientOrderId);
              const persistedSourceContext = tracePersistedSourceContext(
                traceQuery.data.trace,
                correlationId,
                clientOrderId,
              );
              return (
                <>
                  {provenanceLabel ? (
                    <div>
                      <dt>Decision provenance</dt>
                      <dd>{provenanceLabel}</dd>
                    </div>
                  ) : null}
                  {correlationId ? (
                    <div>
                      <dt>Decision correlation</dt>
                      <dd>{correlationId}</dd>
                    </div>
                  ) : null}
                  {persistedSourceContext.snapshotAvailable || persistedSourceContext.snapshotMismatch ? (
                    <div className="trace-source-context">
                      <PaperPersistedSourceContextPanel
                        persisted={persistedSourceContext}
                        compact
                      />
                    </div>
                  ) : null}
                </>
              );
            })()}
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
                <JsonDetailPanel title="Step metadata" value={step.metadata} />
              ) : null}
            </details>
          ))}
        </div>
      ) : null}
    </aside>
  );
}
