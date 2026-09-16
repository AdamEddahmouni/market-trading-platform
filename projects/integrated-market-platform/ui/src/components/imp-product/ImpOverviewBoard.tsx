import type { ReactNode } from "react";
import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import type { Mode } from "../mode-session/types";
import { ImpOverviewKpiStrip } from "./ImpOverviewKpiStrip";
import { ImpOverviewPrimaryQueue, type OverviewQueueFilter } from "./ImpOverviewPrimaryQueue";
import type { OverviewKpiCell } from "./impOverviewMetrics";

export type ImpOverviewBoardProps = {
  kpiCells: OverviewKpiCell[];
  attentionItems: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  attentionEmptyMessage?: string;
  opportunityItems: OpportunityReviewRow[];
  opportunityState: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  mode?: Mode;
  paperAccountId?: string;
  readOnly?: boolean;
  /** Forwarded to the primary queue (Paper defaults to ranked — see queue). */
  defaultQueueFilter?: OverviewQueueFilter;
  onOpportunityRetry?: () => void;
  onAttentionRetry?: () => void;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
  children: ReactNode;
};

export function ImpOverviewBoard({
  kpiCells,
  attentionItems,
  attentionState,
  attentionEmptyMessage,
  opportunityItems,
  opportunityState,
  feedStatus,
  unreadyReason,
  nextAction,
  mode,
  paperAccountId,
  readOnly,
  defaultQueueFilter,
  onOpportunityRetry,
  onAttentionRetry,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
  children,
}: ImpOverviewBoardProps) {
  return (
    <div className="imp-overview-board">
      <ImpOverviewKpiStrip cells={kpiCells} />
      <ImpOverviewPrimaryQueue
        attentionItems={attentionItems}
        attentionState={attentionState}
        attentionEmptyMessage={attentionEmptyMessage}
        opportunityItems={opportunityItems}
        opportunityState={opportunityState}
        feedStatus={feedStatus}
        unreadyReason={unreadyReason}
        nextAction={nextAction}
        mode={mode}
        paperAccountId={paperAccountId}
        readOnly={readOnly}
        defaultFilter={defaultQueueFilter}
        onOpportunityRetry={onOpportunityRetry}
        onAttentionRetry={onAttentionRetry}
        onWhy={onWhy}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
        onAck={onAck}
      />
      <div className="imp-overview-board-body">{children}</div>
    </div>
  );
}
