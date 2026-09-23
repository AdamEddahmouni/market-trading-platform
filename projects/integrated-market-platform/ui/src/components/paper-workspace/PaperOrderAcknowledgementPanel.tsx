import { Link } from "react-router-dom";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import type { PaperOrderAcknowledgement } from "./paperOrderAcknowledgement";

type Props = {
  model: PaperOrderAcknowledgement;
  onViewTrace?: () => void;
  onDismiss?: () => void;
};

export function PaperOrderAcknowledgementPanel({ model, onViewTrace, onDismiss }: Props) {
  const title = model.duplicate
    ? "Paper order already on ledger"
    : model.hasDurableOrder
      ? "Paper order accepted"
      : "Paper submit acknowledged";

  return (
    <section
      className="panel paper-cockpit-panel paper-order-acknowledgement"
      aria-labelledby="paper-order-ack-heading"
      aria-live="polite"
      data-testid="paper-order-acknowledgement"
    >
      <header className="paper-order-ack-header">
        <h2 id="paper-order-ack-heading">{title}</h2>
        {onDismiss ? (
          <button type="button" onClick={onDismiss}>
            Dismiss
          </button>
        ) : null}
      </header>

      <p>
        {model.duplicate
          ? "Idempotent retry — the durable Paper order was already recorded."
          : "Submit reached the Paper ledger. This is internal simulation, not Live broker execution."}
      </p>

      <dl className="metric-list paper-cockpit-meta">
        {model.orderId ? (
          <div>
            <dt>Order ID</dt>
            <dd>
              <CopyableIdentifier value={model.orderId} chars={6} />
            </dd>
          </div>
        ) : (
          <div>
            <dt>Order ID</dt>
            <dd>UNAVAILABLE</dd>
          </div>
        )}
        {model.orderState ? (
          <div>
            <dt>Status</dt>
            <dd>
              <strong>{model.orderState}</strong>
            </dd>
          </div>
        ) : null}
        {model.orderLabel ? (
          <div>
            <dt>Order</dt>
            <dd>{model.orderLabel}</dd>
          </div>
        ) : null}
        {model.instrumentId ? (
          <div>
            <dt>Instrument</dt>
            <dd>{model.instrumentId}</dd>
          </div>
        ) : null}
        {model.intentId ? (
          <div>
            <dt>Intent ID</dt>
            <dd>
              <CopyableIdentifier value={model.intentId} chars={6} />
            </dd>
          </div>
        ) : null}
        {model.provenanceLabel ? (
          <div>
            <dt>Decision source</dt>
            <dd data-testid="paper-order-ack-provenance">{model.provenanceLabel}</dd>
          </div>
        ) : null}
        {model.opportunityId ? (
          <div>
            <dt>Opportunity</dt>
            <dd data-testid="paper-order-ack-opportunity">
              <CopyableIdentifier value={model.opportunityId} chars={8} />
            </dd>
          </div>
        ) : null}
        {model.fillObserved && model.fillId ? (
          <div>
            <dt>Fill</dt>
            <dd>
              Recorded by internal simulation · <CopyableIdentifier value={model.fillId} chars={6} />
            </dd>
          </div>
        ) : (
          <div>
            <dt>Fill</dt>
            <dd className="muted">Not observed on this acknowledgement — order remains durable.</dd>
          </div>
        )}
      </dl>

      <p className="paper-order-ack-actions">
        <Link to={model.orderHistoryHref} data-testid="paper-order-ack-history-link">
          Open Order history
        </Link>
        {onViewTrace && (model.intentId || model.orderId) ? (
          <>
            {" · "}
            <button type="button" className="linkish" onClick={onViewTrace}>
              View execution trace
            </button>
          </>
        ) : null}
      </p>
    </section>
  );
}
