import type { AttentionItem } from "../../api/client";
import { sortPaperCandidates } from "./paperDashboardViewModel";

type Props = {
  items: AttentionItem[]; state: "loading" | "ready" | "error"; selectedAttentionId: string | null;
  onSelect: (attentionId: string) => void; onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void; onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function PaperCandidateQueue({ items, state, selectedAttentionId, onSelect, onWhy, onExplain, onInspect, onOpenWorkspace }: Props) {
  const sorted = sortPaperCandidates(items);
  const hasEligible = sorted.some((item) => Boolean(item.instrument_id?.trim()));
  return (
    <section className="paper-panel paper-candidate-panel" aria-label="Candidate queue">
      <header><h2>Candidate queue</h2><span>{sorted.length} signals</span></header>
      {state === "loading" ? <p role="status">Loading attention feed…</p> : null}
      {state === "error" ? <p role="alert">Attention feed unavailable.</p> : null}
      {state === "ready" ? (
        <div role="radiogroup" aria-label="Paper candidates">
          {sorted.map((item) => {
            const selected = item.attention_id === selectedAttentionId;
            return (
              <article key={item.attention_id} className={`paper-candidate tier-${item.tier ?? 2}${selected ? " selected" : ""}`} aria-selected={selected}>
                <div className="card-head"><h3>{item.headline}</h3>{item.instrument_id ? <code>{item.instrument_id}</code> : null}</div>
                {item.instrument_id ? (
                  <label className="paper-candidate-selector"><input type="radio" name="paper-candidate" checked={selected} onChange={() => onSelect(item.attention_id)} /><span>{item.instrument_id} candidate{selected ? " · Selected candidate" : ""}</span></label>
                ) : <span className="paper-research-only">Research only</span>}
                <ul className="reason-codes">{item.reasons.map((reason) => <li key={reason.code}><code>{reason.code}</code> {reason.label}</li>)}</ul>
                <div className="card-actions">
                  <button type="button" aria-label={`Why here? ${item.headline}`} onClick={() => onWhy(item)}>Why here?</button>
                  <button type="button" aria-label={`Explain ${item.headline}`} onClick={() => onExplain(item)}>Explain</button>
                  <button type="button" aria-label={`Inspect ${item.headline}`} onClick={() => onInspect(item)}>Inspect</button>
                  {item.instrument_id ? (
                    <button
                      type="button"
                      aria-label={`Draft ${item.instrument_id} in Paper workspace`}
                      onClick={() => onOpenWorkspace(item)}
                    >
                      Open in Paper workspace
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
          {!hasEligible ? <p className="unavailable">No instrument-backed candidate is available.</p> : null}
        </div>
      ) : null}
    </section>
  );
}
