import type { ReactNode } from "react";
import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { ImpOverviewKpiStrip } from "./ImpOverviewKpiStrip";
import { ImpTopOpportunityCards } from "./ImpTopOpportunityCards";
import type { OverviewKpiCell, OverviewKpiState } from "./impOverviewMetrics";

export type ImpOverviewBoardProps = {
  kpiCells: OverviewKpiCell[];
  kpiState: OverviewKpiState;
  opportunityItems: OpportunityReviewRow[];
  opportunityState: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  children: ReactNode;
};

export function ImpOverviewBoard({
  kpiCells,
  kpiState,
  opportunityItems,
  opportunityState,
  feedStatus,
  unreadyReason,
  nextAction,
  onExplain,
  onInspect,
  onOpenWorkspace,
  children,
}: ImpOverviewBoardProps) {
  return (
    <div className="imp-overview-board">
      <ImpOverviewKpiStrip cells={kpiCells} state={kpiState} />
      <ImpTopOpportunityCards
        items={opportunityItems}
        state={opportunityState}
        feedStatus={feedStatus}
        unreadyReason={unreadyReason}
        nextAction={nextAction}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
      />
      <div className="imp-overview-board-body">{children}</div>
    </div>
  );
}
