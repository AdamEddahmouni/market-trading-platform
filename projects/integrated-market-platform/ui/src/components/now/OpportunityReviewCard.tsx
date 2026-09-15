import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import { ProgressiveOpportunityCard } from "../imp-product/ProgressiveOpportunityCard";

export type OpportunityReviewCardProps = {
  row: OpportunityReviewRow;
  paperAccountId?: string;
  readOnly?: boolean;
  paperActions?: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

export function explanationRefForRow(row: OpportunityReviewRow): string {
  if (row.explanation_ref) return row.explanation_ref;
  if (row.opportunity_id) return `explain:opportunity:${row.opportunity_id}`;
  return `explain:summary:${row.summary_id}`;
}

export function attentionItemFromOpportunity(row: OpportunityReviewRow): AttentionItem {
  return {
    attention_id: row.summary_id,
    priority_rank: row.rank_order ?? 0,
    headline: row.headline,
    instrument_id: row.instrument_id ?? undefined,
    explanation_ref: explanationRefForRow(row),
    reasons: [],
  };
}

export function OpportunityReviewCard({
  row,
  paperAccountId,
  readOnly = false,
  paperActions = Boolean(paperAccountId),
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: OpportunityReviewCardProps) {
  return (
    <ProgressiveOpportunityCard
      row={row}
      paperAccountId={paperAccountId}
      paperActions={paperActions}
      readOnly={readOnly}
      density="review"
      onExplain={onExplain}
      onInspect={onInspect}
      onOpenWorkspace={onOpenWorkspace}
      onAck={onAck}
    />
  );
}

export type OpportunityReviewListProps = {
  items: OpportunityReviewRow[];
  state: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  paperAccountId?: string;
  readOnly?: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

export function OpportunityReviewList({
  items,
  state,
  feedStatus,
  unreadyReason,
  nextAction,
  paperAccountId,
  readOnly = false,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: OpportunityReviewListProps) {
  if (state === "loading") return <p role="status">Loading opportunity review…</p>;
  if (state === "error") return <p role="alert">Opportunity review unavailable.</p>;
  if (feedStatus === "UNREADY") {
    return (
      <p role="status" className="unavailable">
        Opportunity review is unready{unreadyReason ? ` (${unreadyReason})` : ""}.{" "}
        <a href={nextAction || "/control"}>Open Control Center</a>
      </p>
    );
  }
  if (!items.length) {
    return (
      <p className="unavailable">
        No OpportunityV1 candidates. An empty queue is valid when nothing has been minted.
      </p>
    );
  }
  return (
    <div className="opportunity-review-list">
      {items.map((row) => (
        <OpportunityReviewCard
          key={row.summary_id}
          row={row}
          paperAccountId={paperAccountId}
          readOnly={readOnly}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
          onAck={onAck}
        />
      ))}
    </div>
  );
}
