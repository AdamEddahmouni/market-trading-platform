import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import type { Mode } from "../mode-session/types";
import { OpportunityCard } from "./OpportunityCard";
import { OpportunityFeedState } from "./OpportunityFeedState";
import { stableOpportunityKey } from "./opportunityPresentation";

export type OpportunityQueueProps = {
  items: OpportunityReviewRow[];
  state: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  mode?: Mode;
  paperAccountId?: string;
  readOnly?: boolean;
  onRetry?: () => void;
  emptyReason?: string;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

/**
 * The shared compact opportunity queue for Command and Paper surfaces:
 * one feed-state presentation, one card language. Radar owns the dense
 * table + progressive detail; this queue leads there.
 */
export function OpportunityQueue({
  items,
  state,
  feedStatus,
  unreadyReason,
  nextAction,
  mode,
  paperAccountId,
  readOnly = false,
  onRetry,
  emptyReason,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: OpportunityQueueProps) {
  return (
    <OpportunityFeedState
      state={state}
      feedStatus={feedStatus}
      unreadyReason={unreadyReason}
      nextAction={nextAction}
      mode={mode}
      itemCount={items.length}
      onRetry={onRetry}
      emptyReason={emptyReason}
    >
      <div className="imp-opportunity-queue" data-testid="imp-opportunity-queue">
        {items.map((row) => (
          <OpportunityCard
            key={stableOpportunityKey(row)}
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
    </OpportunityFeedState>
  );
}
