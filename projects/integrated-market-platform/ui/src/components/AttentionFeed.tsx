import { Link } from "react-router-dom";
import type { AttentionItem } from "../api/client";
import {
  attentionTierState,
  attentionWhyNow,
  type AttentionOpportunityLink,
} from "./attentionPresentation";
import { EmptyState, ErrorState } from "./imp-ui/FeedbackStates";
import { FreshnessIndicator } from "./imp-ui/FreshnessIndicator";
import { StatePill } from "./imp-ui/StatePill";
import { LoadingState } from "./shared/LoadingState";

export type AttentionFeedProps = {
  items: AttentionItem[];
  state?: "loading" | "ready" | "error";
  emptyMessage?: string;
  /**
   * Signal→opportunity bridge, keyed by attention id
   * (`attentionOpportunityLinks` on the ranked queue rows). A linked signal
   * shows its ranked state and a Radar path; an unlinked signal shows none —
   * the UI never implies an opportunity that does not exist.
   */
  opportunityLinks?: ReadonlyMap<string, AttentionOpportunityLink>;
  radarPath?: string;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onRetry?: () => void;
};

/**
 * The attention queue: signals and events that need operator review. Signals
 * are their own object class — not opportunities — so cards lead with the
 * signal's why-now (human reason labels), tier urgency, and surfaced timing;
 * raw reason codes stay in the L4 disclosure. When the signal is also ranked
 * in the opportunity queue, a bridge line makes that relationship explicit
 * and links to the Radar detail.
 */
export function AttentionFeed({
  items,
  state = "ready",
  emptyMessage,
  opportunityLinks,
  radarPath = "/radar",
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onRetry,
}: AttentionFeedProps) {
  if (state === "loading") return <LoadingState label="Loading attention feed…" />;
  if (state === "error") {
    return (
      <ErrorState
        title="Attention feed unavailable."
        affects="Signals and events that need review cannot be loaded. Ranked opportunities and Radar remain available."
        onRetry={onRetry}
      />
    );
  }
  if (!items.length) {
    return emptyMessage ? (
      <EmptyState title="Attention queue is clear" reason={emptyMessage} />
    ) : null;
  }

  return (
    <div className="attention-feed">
      {items.map((item) => {
        const tier = attentionTierState(item.tier);
        const whyNow = attentionWhyNow(item);
        const link = opportunityLinks?.get(item.attention_id);
        return (
          <article key={item.attention_id} className={`attention-card tier-${item.tier ?? 2}`}>
            <div className="card-head">
              <div className="attention-card-title">
                <span className="attention-card-kind">Signal</span>
                <h3>{item.headline}</h3>
              </div>
              <div className="attention-card-badges">
                <StatePill tone={tier.tone} label={tier.label} raw={tier.raw} size="sm" />
                {item.instrument_id ? <span className="symbol">{item.instrument_id}</span> : null}
              </div>
            </div>
            {whyNow ? (
              <p className="attention-card-why">
                <span className="attention-card-why-label">Why now:</span> {whyNow}
              </p>
            ) : null}
            {link ? (
              <p className="attention-card-bridge">
                <StatePill tone={link.stateTone} label={link.stateLabel} size="sm" />{" "}
                <span>
                  Also ranked{link.rank ? ` ${link.rank}` : ""} · Evidence {link.evidence} ·{" "}
                  <Link
                    to={`${radarPath}?selected=${encodeURIComponent(link.summaryId)}`}
                    aria-label={`Open ranked opportunity for ${item.headline} in Radar`}
                  >
                    Open in Radar
                  </Link>
                </span>
              </p>
            ) : null}
            <FreshnessIndicator asOf={item.surfaced_time} cadenceSeconds={30} decays={false} />
            {item.reasons.length ? (
              <details className="attention-card-raw">
                <summary>Reason codes</summary>
                <ul className="reason-codes">
                  {item.reasons.map((reason) => (
                    <li key={reason.code}>
                      <code className="reason-code-raw">{reason.code}</code>{" "}
                      <span className="reason-label">{reason.label}</span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
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
        );
      })}
    </div>
  );
}
