import type { AttentionItem } from "../../api/client";
import { attentionTierState } from "../attentionPresentation";
import { ErrorState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { StatePill } from "../imp-ui/StatePill";
import { LoadingState } from "../shared/LoadingState";
import { sortPaperCandidates } from "./paperDashboardViewModel";

type Props = {
  items: AttentionItem[]; state: "loading" | "ready" | "error"; selectedAttentionId: string | null;
  onSelect: (attentionId: string) => void; onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void; onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onRetry?: () => void;
};

/**
 * Paper-Now candidate queue: attention signals the operator can draft from.
 * These are signals, not ranked opportunities — the ranked queue lives on the
 * Command overview and Radar; instrument-backed candidates bridge to the
 * Workspace decision desk. Reason labels are primary (raw codes in tooltips);
 * tier and surfaced timing use the shared attention language.
 */
export function PaperCandidateQueue({
  items, state, selectedAttentionId, onSelect, onWhy, onExplain, onInspect, onOpenWorkspace, onRetry,
}: Props) {
  const sorted = sortPaperCandidates(items);
  const hasEligible = sorted.some((item) => Boolean(item.instrument_id?.trim()));
  return (
    <section className="paper-panel paper-candidate-panel" aria-label="Candidate queue">
      <header><h2>Candidate queue</h2><span>{sorted.length} signals</span></header>
      {state === "loading" ? <LoadingState label="Loading attention feed…" /> : null}
      {state === "error" ? (
        <ErrorState
          title="Attention feed unavailable."
          affects="Candidates cannot be loaded. Ranked opportunities on the Command overview remain available."
          onRetry={onRetry}
        />
      ) : null}
      {state === "ready" ? (
        <div role="radiogroup" aria-label="Paper candidates">
          {sorted.map((item) => {
            const selected = item.attention_id === selectedAttentionId;
            const tier = attentionTierState(item.tier);
            return (
              <article key={item.attention_id} className={`paper-candidate tier-${item.tier ?? 2}${selected ? " selected" : ""}`} aria-selected={selected}>
                <div className="card-head"><h3>{item.headline}</h3>{item.instrument_id ? <code>{item.instrument_id}</code> : null}</div>
                <div className="paper-candidate-context">
                  <StatePill tone={tier.tone} label={tier.label} raw={tier.raw} size="sm" />
                  <FreshnessIndicator asOf={item.surfaced_time} cadenceSeconds={30} decays={false} />
                </div>
                {item.instrument_id ? (
                  <label className="paper-candidate-selector"><input type="radio" name="paper-candidate" checked={selected} onChange={() => onSelect(item.attention_id)} /><span>{item.instrument_id} candidate{selected ? " · Selected candidate" : ""}</span></label>
                ) : <span className="paper-research-only">Research only</span>}
                <ul className="reason-codes">{item.reasons.map((reason) => <li key={reason.code} title={reason.code}><span className="reason-label">{reason.label}</span></li>)}</ul>
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
