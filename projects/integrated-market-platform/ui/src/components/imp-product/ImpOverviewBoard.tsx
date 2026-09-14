import type { ReactNode } from "react";
import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import { ImpOverviewKpiStrip } from "./ImpOverviewKpiStrip";
import { ImpOverviewPrimaryQueue } from "./ImpOverviewPrimaryQueue";
import type { OverviewKpiCell, OverviewKpiState } from "./impOverviewMetrics";

export type ImpOverviewBoardProps = {
  kpiCells: OverviewKpiCell[];
  kpiState: OverviewKpiState;
  attentionItems: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  attentionEmptyMessage?: string;
  opportunityItems: OpportunityReviewRow[];
  opportunityState: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  paperAccountId?: string;
  readOnly?: boolean;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
  children: ReactNode;
};

export function ImpOverviewBoard({
  kpiCells,
  kpiState,
  attentionItems,
  attentionState,
  attentionEmptyMessage,
  opportunityItems,
  opportunityState,
  feedStatus,
  unreadyReason,
  nextAction,
  paperAccountId,
  readOnly,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
  children,
}: ImpOverviewBoardProps) {
  return (
    <div className="imp-overview-board">
      <ImpOverviewKpiStrip cells={kpiCells} state={kpiState} />
      <ImpOverviewPrimaryQueue
        attentionItems={attentionItems}
        attentionState={attentionState}
        attentionEmptyMessage={attentionEmptyMessage}
        opportunityItems={opportunityItems}
        opportunityState={opportunityState}
        feedStatus={feedStatus}
        unreadyReason={unreadyReason}
        nextAction={nextAction}
        paperAccountId={paperAccountId}
        readOnly={readOnly}
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
