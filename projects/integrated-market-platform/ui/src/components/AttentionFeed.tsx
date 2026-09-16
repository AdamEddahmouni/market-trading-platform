import type { AttentionItem } from "../api/client";
import { FreshnessIndicator } from "./imp-ui/FreshnessIndicator";

export type AttentionFeedProps = {
  items: AttentionItem[];
  state?: "loading" | "ready" | "error";
  emptyMessage?: string;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

const TIER_LABEL: Record<number, string> = {
  1: "Tier 1 — act now",
  2: "Tier 2 — review",
  3: "Tier 3 — monitor",
};

export function tierLabel(tier: number | undefined): string {
  if (tier == null) return "Tier 2 — review";
  return TIER_LABEL[tier] ?? `Tier ${tier}`;
}

export function AttentionFeed({
  items,
  state = "ready",
  emptyMessage,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: AttentionFeedProps) {
  if (state === "loading") return <p role="status">Loading attention feed…</p>;
  if (state === "error") return <p role="alert">Attention feed unavailable.</p>;
  if (!items.length) return emptyMessage ? <p className="unavailable">{emptyMessage}</p> : null;

  return (
    <div className="attention-feed">
      {items.map((item) => (
        <article key={item.attention_id} className={`attention-card tier-${item.tier ?? 2}`}>
          <div className="card-head">
            <div className="attention-card-title">
              <span className="attention-tier-label" data-tier={item.tier ?? 2}>
                {tierLabel(item.tier)}
              </span>
              <h2>{item.headline}</h2>
            </div>
            {item.instrument_id ? <span className="symbol">{item.instrument_id}</span> : null}
          </div>
          {item.surfaced_time ? (
            <FreshnessIndicator asOf={item.surfaced_time} cadenceSeconds={30} />
          ) : null}
          <ul className="reason-codes">
            {item.reasons.map((reason) => (
              <li key={reason.code}>
                <span className="reason-label">{reason.label}</span>{" "}
                <code className="reason-code-raw" title="Raw reason code">
                  {reason.code}
                </code>
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
  );
}
