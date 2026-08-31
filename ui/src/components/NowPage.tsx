import type { AttentionItem } from "../api/client";
import type { ChartCountPoint } from "../lib/chartTransforms";
import { AttentionFeed } from "./AttentionFeed";
import { CountBarChartPanel } from "./charts/ResearchChartPanels";

export type NowPageProps = {
  items: AttentionItem[];
  tierSummary?: ChartCountPoint[];
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function NowPage({ items, tierSummary, onWhy, onExplain, onInspect, onOpenWorkspace }: NowPageProps) {
  return (
    <section className="page now-page">
      <header className="page-header">
        <h1>Command Center</h1>
        <p>Attention-prioritized feed with reason codes — no opaque rank score.</p>
      </header>
      {tierSummary ? (
        <div className="chart-grid chart-grid-inline">
          <CountBarChartPanel
            title="Attention tiers (full feed)"
            series={tierSummary}
            provenance={{ source: "replay attention feed", method: "tier aggregation at cutoff" }}
            ariaLabel="Attention tier distribution chart"
          />
        </div>
      ) : null}
      <AttentionFeed
        items={items}
        onWhy={onWhy}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
      />
    </section>
  );
}
