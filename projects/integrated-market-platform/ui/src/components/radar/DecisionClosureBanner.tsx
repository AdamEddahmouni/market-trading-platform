import type { OpportunityAckAction } from "../../api/opportunityClient";
import { useTradeReviewsQuery } from "../../api/tradeReviewClient";
import type { TradeReviewAckPhase } from "../imp-product/TradeReviewLearningPanel";

export type DecisionClosureRecord = {
  opportunityId: string;
  summaryId: string;
  instrumentId: string | null;
  headline: string;
  action: OpportunityAckAction;
  tradeReviewId?: string;
  decisionTraceMode?: string;
  leftActiveQueue: boolean;
};

type Props = {
  closure: DecisionClosureRecord;
  phase: TradeReviewAckPhase;
  onRetryReconcile?: () => void;
  onDismissBanner?: () => void;
};

/**
 * Compact post-action closure for Watch/Dismiss. Shows authoritative durable
 * review identity after reconciliation. Used especially when Dismiss removes
 * the row from the active queue so the operator still has inspectable evidence.
 */
export function DecisionClosureBanner({
  closure,
  phase,
  onRetryReconcile,
  onDismissBanner,
}: Props) {
  const query = useTradeReviewsQuery(
    closure.opportunityId,
    phase === "completed" || phase === "reconciliation_failed" || phase === "synchronizing",
  );
  const items = query.data?.items ?? [];
  const actionLabel =
    closure.action === "watch" ? "Watch" : closure.action === "dismiss" ? "Dismiss" : "Review";

  return (
    <aside
      className="panel mode-restriction-note"
      data-testid="decision-closure-banner"
      role="status"
      aria-label="Operator decision closure"
    >
      <strong>
        {actionLabel} accepted
        {closure.leftActiveQueue ? " — left active queue" : ""}
      </strong>
      <p>
        Opportunity <code>{closure.opportunityId}</code>
        {closure.instrumentId ? (
          <>
            {" "}
            · <code>{closure.instrumentId}</code>
          </>
        ) : null}
        {closure.headline ? ` — ${closure.headline}` : ""}
      </p>
      {closure.decisionTraceMode ? (
        <p className="muted">DecisionTrace mode: {closure.decisionTraceMode}</p>
      ) : null}
      {phase === "synchronizing" ? (
        <p className="muted">Synchronizing durable DecisionTrace / TradeReview…</p>
      ) : null}
      {phase === "reconciliation_failed" ? (
        <p className="unavailable" role="alert">
          Action accepted
          {closure.tradeReviewId ? ` (review ${closure.tradeReviewId})` : ""}, but durable review
          retrieval failed.
          {onRetryReconcile ? (
            <>
              {" "}
              <button type="button" onClick={onRetryReconcile}>
                Retry review retrieval
              </button>
            </>
          ) : null}
        </p>
      ) : null}
      {phase === "completed" && items.length ? (
        <ul className="imp-opportunity-lines">
          {items.map((item) => (
            <li key={item.review_id}>
              <strong>{item.review_mode}</strong> · {item.decision}
              <span className="muted"> ({item.review_id})</span>
            </li>
          ))}
        </ul>
      ) : null}
      {phase === "completed" && !items.length && closure.tradeReviewId ? (
        <p className="muted">Durable review id: {closure.tradeReviewId}</p>
      ) : null}
      {onDismissBanner ? (
        <p>
          <button type="button" onClick={onDismissBanner}>
            Dismiss notice
          </button>
        </p>
      ) : null}
    </aside>
  );
}
