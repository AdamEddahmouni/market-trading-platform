import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { useTradeReviewsQuery } from "../../api/tradeReviewClient";

type Props = {
  row: OpportunityReviewRow;
};

export function TradeReviewLearningPanel({ row }: Props) {
  const opportunityId = row.opportunity_id ?? row.summary_id;
  const query = useTradeReviewsQuery(opportunityId, Boolean(opportunityId));
  const items = query.data?.items ?? [];

  if (!opportunityId) {
    return null;
  }

  if (query.isLoading) {
    return <p className="muted">Loading durable trade review…</p>;
  }

  if (query.isError) {
    return <p className="unavailable">Trade review UNAVAILABLE (fixture/replay API path only).</p>;
  }

  if (!items.length) {
    return (
      <p className="muted">
        No durable trade review yet. Dismiss or watch to materialize a learning record (replay/Paper).
      </p>
    );
  }

  return (
    <div className="trade-review-learning-panel">
      <p className="imp-section-eyebrow">Durable learning record</p>
      <ul className="progressive-opp-lines">
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
