import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { useTradeReviewsQuery } from "../../api/tradeReviewClient";

export type TradeReviewAckPhase =
  | "idle"
  | "submitting"
  | "synchronizing"
  | "completed"
  | "failed"
  | "reconciliation_failed";

type Props = {
  row: OpportunityReviewRow;
  /** Transient operator-ack lifecycle for this detail surface. */
  ackPhase?: TradeReviewAckPhase;
  /** Backend trade_review_id returned by the successful ack, when present. */
  expectedReviewId?: string | null;
  onRetryReconcile?: () => void;
};

export function TradeReviewLearningPanel({
  row,
  ackPhase = "idle",
  expectedReviewId = null,
  onRetryReconcile,
}: Props) {
  const opportunityId = row.opportunity_id ?? row.summary_id;
  const query = useTradeReviewsQuery(opportunityId, Boolean(opportunityId));
  const items = query.data?.items ?? [];
  const fetching = query.isFetching || query.isLoading;

  if (!opportunityId) {
    return null;
  }

  if (ackPhase === "submitting") {
    return <p className="muted" role="status">Submitting operator decision…</p>;
  }

  if (ackPhase === "synchronizing") {
    return (
      <p className="muted" role="status">
        Action accepted — synchronizing durable trade review…
      </p>
    );
  }

  if (ackPhase === "failed") {
    return (
      <p className="unavailable" role="alert">
        Operator action failed. Previous durable review state was not changed by this attempt.
      </p>
    );
  }

  if (ackPhase === "reconciliation_failed") {
    return (
      <div className="trade-review-learning-panel" role="alert">
        <p className="unavailable">
          Action was accepted by the backend
          {expectedReviewId ? ` (review ${expectedReviewId})` : ""}, but the durable trade review
          could not be retrieved yet.
        </p>
        {onRetryReconcile ? (
          <button type="button" onClick={onRetryReconcile}>
            Retry review retrieval
          </button>
        ) : null}
      </div>
    );
  }

  if (fetching && !items.length) {
    return <p className="muted">Loading durable trade review…</p>;
  }

  if (query.isError) {
    return (
      <div className="trade-review-learning-panel" role="alert">
        <p className="unavailable">
          Trade review retrieval failed
          {expectedReviewId
            ? ` after action accepted (review ${expectedReviewId}).`
            : " (fixture/replay API path only)."}
        </p>
        {onRetryReconcile ? (
          <button type="button" onClick={onRetryReconcile}>
            Retry review retrieval
          </button>
        ) : null}
      </div>
    );
  }

  if (!items.length) {
    if (expectedReviewId) {
      return (
        <div className="trade-review-learning-panel" role="alert">
          <p className="unavailable">
            Action accepted (review {expectedReviewId}), but no durable trade review is visible yet.
          </p>
          {onRetryReconcile ? (
            <button type="button" onClick={onRetryReconcile}>
              Retry review retrieval
            </button>
          ) : null}
        </div>
      );
    }
    return (
      <p className="muted">
        No durable trade review yet. Dismiss or watch to materialize a learning record (replay/Paper).
      </p>
    );
  }

  return (
    <div className="trade-review-learning-panel" data-testid="trade-review-learning-panel">
      <p className="imp-section-eyebrow">Durable learning record</p>
      <ul className="imp-opportunity-lines">
        {items.map((item) => (
          <li key={item.review_id}>
            <strong>{item.review_mode}</strong> · {item.decision}
            {item.notes ? ` — ${item.notes}` : ""}
            <span className="muted"> ({item.review_id})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
