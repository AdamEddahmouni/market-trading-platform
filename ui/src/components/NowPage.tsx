import type { AttentionItem } from "../api/client";
import type { ChartCountPoint } from "../lib/chartTransforms";
import { CountBarChartPanel } from "./charts/ResearchChartPanels";

type Props = {
  items: AttentionItem[];
  tierSummary?: ChartCountPoint[];
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function NowPage({ items, tierSummary, onWhy, onExplain, onInspect, onOpenWorkspace }: Props) {
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
      <div className="attention-feed">
        {items.map((item) => (
          <article key={item.attention_id} className={`attention-card tier-${item.tier ?? 2}`}>
            <div className="card-head">
              <h2>{item.headline}</h2>
              {item.instrument_id ? <span className="symbol">{item.instrument_id}</span> : null}
            </div>
            <ul className="reason-codes">
              {item.reasons.map((reason) => (
                <li key={reason.code}>
                  <code>{reason.code}</code> {reason.label}
                </li>
              ))}
            </ul>
            <div className="card-actions">
              <button type="button" onClick={() => onWhy(item)}>
                Why here?
              </button>
              <button type="button" onClick={() => onExplain(item)}>
                Explain
              </button>
              <button type="button" onClick={() => onInspect(item)}>
                Inspect
              </button>
              {item.instrument_id ? (
                <button type="button" onClick={() => onOpenWorkspace(item)}>
                  Open workspace
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
