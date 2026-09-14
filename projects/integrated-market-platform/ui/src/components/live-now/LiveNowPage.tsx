import type { AttentionItem } from "../../api/client";
import { useOpportunitiesSummaryQuery } from "../../api/opportunityClient";
import { AttentionFeed } from "../AttentionFeed";
import { ImpOverviewBoard } from "../imp-product/ImpOverviewBoard";
import { overviewKpisFromLiveContext } from "../imp-product/impOverviewMetrics";
import type { LiveCanarySnapshot } from "./liveCanarySnapshot";
import { LiveProviderRibbon } from "./LiveProviderRibbon";
import { LiveSafetySnapshot } from "./LiveSafetySnapshot";
import { LiveSymbolLookup } from "./LiveSymbolLookup";
import type { ProviderHealthResponse } from "./liveDashboardViewModel";

export type LiveNowPageProps = {
  items: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  dataMode?: string;
  executionAuthority?: string;
  providerHealth?: ProviderHealthResponse;
  providerState: "loading" | "ready" | "error";
  canarySnapshot?: LiveCanarySnapshot;
  safetyState: "loading" | "ready" | "error";
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function LiveNowPage({
  items,
  attentionState,
  dataMode,
  executionAuthority,
  providerHealth,
  providerState,
  canarySnapshot,
  safetyState,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: LiveNowPageProps) {
  const opportunitiesQuery = useOpportunitiesSummaryQuery(true);
  const opportunityState = opportunitiesQuery.isLoading
    ? "loading"
    : opportunitiesQuery.isError || !opportunitiesQuery.data
      ? "error"
      : "ready";
  const contextReady = providerState !== "loading";
  const kpiState = !contextReady ? "loading" : providerState === "error" ? "error" : "ready";
  const kpiCells = overviewKpisFromLiveContext({
    state: kpiState,
    attentionCount: items.length,
    dataMode,
    executionAuthority,
    providerName: providerHealth?.provider_summary?.provider,
    connectionState: providerHealth?.lifecycle?.connection_state,
    opportunityFeedStatus: opportunitiesQuery.data?.feed_status,
  });

  return (
    <section className="page live-now-page">
      <header className="live-now-header">
        <div>
          <span className="live-eyebrow">Live · Read-only observational</span>
          <h1>Live Watch</h1>
          <p>
            Monitor current market data, provider health, and operational safety without execution
            authority. Use workspaces for instrument-level observation only.
          </p>
        </div>
        <dl>
          <div>
            <dt>Data mode</dt>
            <dd>{dataMode?.replace(/_/g, " ") ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Execution authority</dt>
            <dd>{executionAuthority?.replace(/_/g, " ") ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Provider</dt>
            <dd>{providerHealth?.provider_summary?.provider ?? "Unavailable"}</dd>
          </div>
          <div>
            <dt>Connection</dt>
            <dd>{providerHealth?.lifecycle?.connection_state ?? "Unavailable"}</dd>
          </div>
        </dl>
      </header>

      <ImpOverviewBoard
        kpiCells={kpiCells}
        kpiState={kpiState}
        opportunityItems={opportunitiesQuery.data?.items ?? []}
        opportunityState={opportunityState}
        feedStatus={opportunitiesQuery.data?.feed_status}
        unreadyReason={opportunitiesQuery.data?.unready_reason}
        nextAction={opportunitiesQuery.data?.next_action}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
      >
      <LiveProviderRibbon health={providerHealth} state={providerState} />

      <div className="live-now-grid live-now-grid-top">
        <LiveSafetySnapshot snapshot={canarySnapshot} state={safetyState} />
        <LiveSymbolLookup health={providerHealth} state={providerState} />
      </div>

      <section className="live-panel live-attention-panel" aria-labelledby="live-attention-title">
        <header className="live-panel-heading">
          <div>
            <p className="live-eyebrow">Evidence queue</p>
            <h2 id="live-attention-title">What matters now</h2>
          </div>
        </header>
        <AttentionFeed
          items={items}
          state={attentionState}
          emptyMessage="Nothing requires attention in the current live feed."
          onWhy={onWhy}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      </section>
      </ImpOverviewBoard>
    </section>
  );
}
