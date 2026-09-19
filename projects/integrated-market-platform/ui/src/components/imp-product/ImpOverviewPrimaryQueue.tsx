import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import type { Mode } from "../mode-session/types";
import { AttentionFeed } from "../AttentionFeed";
import { OpportunityQueue } from "../opportunity/OpportunityQueue";
import { attentionOpportunityLinks } from "../opportunity/opportunityPresentation";

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
  mode?: Mode;
  radarPath?: string;
  paperAccountId?: string;
  readOnly?: boolean;
  /**
   * Default queue view. "both" shows opportunities and attention together;
   * Paper passes "ranked" because its decision grid already presents the
   * attention signals as the candidate queue — each information class
   * appears once per page.
   */
  defaultFilter?: OverviewQueueFilter;
  onOpportunityRetry?: () => void;
  onAttentionRetry?: () => void;
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

/**
 * Command's primary queue: the ranked opportunity queue (shared opportunity
 * primitives — same state/evidence/freshness/next-action language as Radar)
 * alongside the attention signal queue. Both queues are visible by default —
 * "what is actionable" and "what needs review" are the page's core questions;
 * the tabs offer focused views. Compact and high-signal; deep detail lives
 * on Radar.
 */
export function ImpOverviewPrimaryQueue({
  attentionItems,
  attentionState,
  attentionEmptyMessage = "Nothing requires attention right now.",
  opportunityItems,
  opportunityState,
  feedStatus,
  unreadyReason,
  nextAction,
  mode,
  radarPath = "/radar",
  paperAccountId,
  readOnly = false,
  defaultFilter = "both",
  onOpportunityRetry,
  onAttentionRetry,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: ImpOverviewPrimaryQueueProps) {
  const [filter, setFilter] = useState<OverviewQueueFilter>(defaultFilter);
  const showRanked = filter === "ranked" || filter === "both";
  const showAttention = filter === "attention" || filter === "both";
  const opportunityLinks = useMemo(
    () => attentionOpportunityLinks(opportunityItems),
    [opportunityItems],
  );

  const rankedCount = opportunityState === "ready" ? opportunityItems.length : null;
  const attentionCount = attentionState === "ready" ? attentionItems.length : null;
  const tabLabel = (entry: (typeof FILTERS)[number]): string => {
    if (entry.id === "ranked") return rankedCount != null ? `Ranked (${rankedCount})` : "Ranked";
    if (entry.id === "attention") {
      return attentionCount != null ? `Attention (${attentionCount})` : "Attention";
    }
    return "Both";
  };

  function onTabsKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const index = FILTERS.findIndex((entry) => entry.id === filter);
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % FILTERS.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + FILTERS.length) % FILTERS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = FILTERS.length - 1;
    if (next < 0) return;
    event.preventDefault();
    const target = FILTERS[next];
    setFilter(target.id);
    document.getElementById(`imp-overview-queue-tab-${target.id}`)?.focus();
  }

  return (
    <section className="imp-overview-primary-queue" aria-labelledby="imp-overview-primary-queue-title">
      <header className="imp-overview-primary-queue-header">
        <div>
          <p className="imp-section-eyebrow">Opportunity Radar</p>
          <h2 id="imp-overview-primary-queue-title">Primary review queue</h2>
        </div>
        <Link className="imp-overview-radar-link" to={radarPath}>
          Open full radar
        </Link>
      </header>

      <div
        className="imp-overview-queue-filters"
        role="tablist"
        aria-label="Queue source"
        onKeyDown={onTabsKeyDown}
      >
        {FILTERS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`imp-overview-queue-tab-${entry.id}`}
            aria-selected={filter === entry.id}
            aria-controls={
              filter === entry.id ? `imp-overview-queue-panel-${entry.id}` : undefined
            }
            tabIndex={filter === entry.id ? 0 : -1}
            className={filter === entry.id ? "active" : undefined}
            onClick={() => setFilter(entry.id)}
          >
            {tabLabel(entry)}
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
            <h3 className="imp-overview-queue-subhead">Ranked opportunities</h3>
            <OpportunityQueue
              items={opportunityItems}
              state={opportunityState}
              feedStatus={feedStatus}
              unreadyReason={unreadyReason}
              nextAction={nextAction}
              mode={mode}
              paperAccountId={paperAccountId}
              readOnly={readOnly}
              onRetry={onOpportunityRetry}
              onExplain={onExplain}
              onInspect={onInspect}
              onOpenWorkspace={onOpenWorkspace}
              onAck={onAck}
            />
          </div>
        ) : null}
        {showAttention ? (
          <div className="imp-overview-queue-attention">
            <h3 className="imp-overview-queue-subhead">Attention queue</h3>
            <AttentionFeed
              items={attentionItems}
              state={attentionState}
              emptyMessage={attentionEmptyMessage}
              opportunityLinks={opportunityLinks}
              radarPath={radarPath}
              onWhy={onWhy}
              onExplain={onExplain}
              onInspect={onInspect}
              onOpenWorkspace={onOpenWorkspace}
              onRetry={onAttentionRetry}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
