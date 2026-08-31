import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { AttentionFeed } from "../AttentionFeed";
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
  const progress = props.replayState === "ready" ? deriveReplayProgress(props.cursorIndex, props.eventCount) : null;
  const canAdvance = Boolean(progress?.hasNext);
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
    </div>
  );
}
