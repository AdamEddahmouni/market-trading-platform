import { useState } from "react";
import { Link } from "react-router-dom";
import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import { AttentionFeed } from "../AttentionFeed";
import { OpportunityReviewList } from "../now/OpportunityReviewCard";
import { OpportunityFeedStatusBanner } from "./OpportunityFeedStatusBanner";

export type OverviewQueueFilter = "ranked" | "attention" | "both";

export type ImpOverviewPrimaryQueueProps = {
  attentionItems: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  attentionEmptyMessage?: string;
  opportunityItems: OpportunityReviewRow[];
  opportunityState: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  discoverPath?: string;
  paperAccountId?: string;
  readOnly?: boolean;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

const FILTERS: { id: OverviewQueueFilter; label: string }[] = [
  { id: "ranked", label: "Ranked" },
  { id: "attention", label: "Attention" },
  { id: "both", label: "Both" },
];

export function ImpOverviewPrimaryQueue({
  attentionItems,
  attentionState,
  attentionEmptyMessage = "Nothing requires attention right now.",
  opportunityItems,
  opportunityState,
  feedStatus,
  unreadyReason,
  nextAction,
  discoverPath = "/discover",
  paperAccountId,
  readOnly = false,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: ImpOverviewPrimaryQueueProps) {
  const [filter, setFilter] = useState<OverviewQueueFilter>("ranked");
  const showRanked = filter === "ranked" || filter === "both";
  const showAttention = filter === "attention" || filter === "both";

  return (
    <section className="imp-overview-primary-queue" aria-labelledby="imp-overview-primary-queue-title">
      <header className="imp-overview-primary-queue-header">
        <div>
          <p className="imp-section-eyebrow">Opportunity Radar</p>
          <h2 id="imp-overview-primary-queue-title">Primary review queue</h2>
        </div>
        <Link className="imp-top-opportunities-link" to={discoverPath}>
          Open full radar
        </Link>
      </header>

      <div className="imp-overview-queue-filters" role="tablist" aria-label="Queue source">
        {FILTERS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`imp-overview-queue-tab-${entry.id}`}
            aria-selected={filter === entry.id}
            aria-controls={`imp-overview-queue-panel-${entry.id}`}
            className={filter === entry.id ? "active" : undefined}
            onClick={() => setFilter(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div
        className="imp-overview-queue-panels"
        role="tabpanel"
        id={`imp-overview-queue-panel-${filter}`}
        aria-labelledby={`imp-overview-queue-tab-${filter}`}
      >
        {showRanked ? (
          <div className="imp-overview-queue-ranked">
            <OpportunityFeedStatusBanner
              state={opportunityState}
              feedStatus={feedStatus}
              unreadyReason={unreadyReason}
              nextAction={nextAction}
            />
            <OpportunityReviewList
              items={opportunityItems}
              state={opportunityState}
              feedStatus={feedStatus}
              unreadyReason={unreadyReason}
              nextAction={nextAction}
              paperAccountId={paperAccountId}
              readOnly={readOnly}
              onExplain={onExplain}
              onInspect={onInspect}
              onOpenWorkspace={onOpenWorkspace}
              onAck={onAck}
            />
          </div>
        ) : null}
        {showAttention ? (
          <div className="imp-overview-queue-attention">
            <AttentionFeed
              items={attentionItems}
              state={attentionState}
              emptyMessage={attentionEmptyMessage}
              onWhy={onWhy}
              onExplain={onExplain}
              onInspect={onInspect}
              onOpenWorkspace={onOpenWorkspace}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
