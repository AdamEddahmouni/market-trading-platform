import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { useOpportunitiesSummaryQuery } from "../../api/opportunityClient";
import { AttentionFeed } from "../AttentionFeed";
import { OpportunityReviewList } from "../now/OpportunityReviewCard";
import { ImpOverviewBoard } from "../imp-product/ImpOverviewBoard";
import { overviewKpisFromPortfolio } from "../imp-product/impOverviewMetrics";
import { DemoInspectNext } from "./DemoInspectNext";
import { DemoPortfolioSummary } from "./DemoPortfolioSummary";
import { DemoReplayOverview, deriveReplayProgress } from "./DemoReplayOverview";

export type LoadState = "loading" | "ready" | "error";
export type ScrubState = "idle" | "pending" | "error";

export type DemoNowPageProps = {
  items: AttentionItem[];
  attentionState: LoadState;
  replayState: LoadState;
  cursorIndex: number;
  eventCount?: number;
  scrubState: ScrubState;
  portfolioState: LoadState;
  portfolio?: PaperPortfolioResponse;
  onScrub: (index: number) => void;
  onOpenTimeline: () => void;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function DemoNowPage(props: DemoNowPageProps) {
  const opportunitiesQuery = useOpportunitiesSummaryQuery(true);
  const opportunityState = opportunitiesQuery.isLoading
    ? "loading"
    : opportunitiesQuery.isError || !opportunitiesQuery.data
      ? "error"
      : "ready";
  const progress = props.replayState === "ready" ? deriveReplayProgress(props.cursorIndex, props.eventCount) : null;
  const canAdvance = Boolean(progress?.hasNext);
  const kpiState =
    props.portfolioState === "loading"
      ? "loading"
      : props.portfolioState === "error"
        ? "error"
        : "ready";
  const kpiCells = overviewKpisFromPortfolio(props.portfolio, kpiState);
  return (
    <div className="page demo-now-page">
      <header className="demo-now-intro">
        <div>
          <p className="demo-eyebrow">Demo · Historical research</p>
          <h1>See the market unfold</h1>
          <p>
            Move through a known historical sequence, inspect the evidence at each event, and learn without
            execution risk.
          </p>
        </div>
        <span className="demo-intro-mark">BIYA / REPLAY</span>
      </header>
      <ImpOverviewBoard
        kpiCells={kpiCells}
        kpiState={kpiState}
        opportunityItems={opportunitiesQuery.data?.items ?? []}
        opportunityState={opportunityState}
        feedStatus={opportunitiesQuery.data?.feed_status}
        unreadyReason={opportunitiesQuery.data?.unready_reason}
        nextAction={opportunitiesQuery.data?.next_action}
        onExplain={props.onExplain}
        onInspect={props.onInspect}
        onOpenWorkspace={props.onOpenWorkspace}
      >
      <div className="demo-now-grid demo-now-grid-top">
        <DemoReplayOverview
          cursorIndex={props.cursorIndex}
          eventCount={props.eventCount}
          state={props.replayState}
          scrubState={props.scrubState}
          onScrub={props.onScrub}
          onOpenTimeline={props.onOpenTimeline}
        />
        <DemoPortfolioSummary state={props.portfolioState} portfolio={props.portfolio} />
      </div>
      <div className="demo-now-grid demo-now-grid-bottom">
        <section className="demo-now-panel demo-attention-panel" aria-labelledby="demo-attention-title">
          <div className="demo-panel-heading">
            <div>
              <p className="demo-eyebrow">Evidence queue</p>
              <h2 id="demo-attention-title">What matters now</h2>
            </div>
          </div>
          <OpportunityReviewList
            items={opportunitiesQuery.data?.items ?? []}
            state={opportunityState}
            feedStatus={opportunitiesQuery.data?.feed_status}
            unreadyReason={opportunitiesQuery.data?.unready_reason}
            nextAction={opportunitiesQuery.data?.next_action}
            readOnly
            onExplain={props.onExplain}
            onInspect={props.onInspect}
            onOpenWorkspace={props.onOpenWorkspace}
          />
          <AttentionFeed
            items={props.items}
            state={props.attentionState}
            emptyMessage="Nothing requires attention at the current event."
            onWhy={props.onWhy}
            onExplain={props.onExplain}
            onInspect={props.onInspect}
            onOpenWorkspace={props.onOpenWorkspace}
          />
        </section>
        <DemoInspectNext
          items={props.items}
          canAdvance={canAdvance}
          replayPending={props.scrubState === "pending"}
          onExplain={props.onExplain}
          onInspect={props.onInspect}
          onOpenWorkspace={props.onOpenWorkspace}
          onAdvance={() => {
            if (progress?.hasNext) props.onScrub(progress.cursorIndex + 1);
          }}
        />
      </div>
      </ImpOverviewBoard>
    </div>
  );
}
