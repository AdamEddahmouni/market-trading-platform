import type { AttentionItem } from "../api/client";

export type AttentionFeedProps = {
  items: AttentionItem[];
  state?: "loading" | "ready" | "error";
  emptyMessage?: string;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

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
  );
}
