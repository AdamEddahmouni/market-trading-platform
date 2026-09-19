import type { ReactNode } from "react";
import { resolveSemanticState } from "../../state/semanticState";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { EmptyState, ErrorState } from "../imp-ui/FeedbackStates";
import { LoadingState } from "../shared/LoadingState";
import type { Mode } from "../mode-session/types";
import { humanizeUnreadyReason } from "./opportunityPresentation";
import {
  buildLiveWithheldOperatorBrief,
  liveFeedClockHonesty,
} from "./opportunityOperatorBrief";
import { matchKnownDataIncident } from "../operator-shared/knownDataIncidents";
import { PrecisionFailureBanner } from "../imp-ui/PrecisionFailureBanner";

export type OpportunityFeedStateProps = {
  state: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  /** Live treats an UNAVAILABLE feed as by-design (no opportunity engine). */
  mode?: Mode;
  itemCount: number;
  onRetry?: () => void;
  /** Page-specific empty reason; defaults to the canonical empty-queue copy. */
  emptyReason?: string;
  /** Ranked rows withheld for missing live receive clock (optional honesty). */
  withheldRankedCount?: number;
  /** Backend book honesty token when ranked live rows are withheld. */
  bookHonesty?: string;
  /** Rendered only when the queue is ready with items. */
  children: ReactNode;
};

function controlHref(nextAction?: string): string {
  if (!nextAction) return "/control#control-feed";
  if (nextAction.startsWith("/")) return nextAction;
  return "/control#control-feed";
}

/**
 * The one feed-state presentation for the opportunity queue: loading, error,
 * UNREADY, UNAVAILABLE, and empty all mean the same thing on every surface.
 * Renders `children` only when the queue is ready with items.
 */
export function OpportunityFeedState({
  state,
  feedStatus,
  unreadyReason,
  nextAction,
  mode,
  itemCount,
  onRetry,
  emptyReason = "An empty queue is valid: nothing has been minted for the current coverage.",
  withheldRankedCount,
  bookHonesty,
  children,
}: OpportunityFeedStateProps) {
  if (state === "loading") {
    return <LoadingState label="Loading ranked opportunities…" />;
  }

  if (state === "error") {
    return (
      <ErrorState
        title="Opportunity ranking is unavailable."
        affects="The ranked queue cannot be loaded. Screeners and workspace evidence remain available."
        onRetry={onRetry}
      />
    );
  }

  if (feedStatus === "UNREADY") {
    const incident = matchKnownDataIncident(unreadyReason);
    if (incident) {
      return (
        <PrecisionFailureBanner incident={incident}>
          {unreadyReason ? (
            <span className="imp-radar-muted" title="Raw reason code">
              Code: {unreadyReason}
            </span>
          ) : null}
        </PrecisionFailureBanner>
      );
    }
    const reason = humanizeUnreadyReason(unreadyReason);
    const unready = resolveSemanticState("research", "UNREADY", {
      params: { reason: reason ?? "" },
    });
    const clockHonesty = liveFeedClockHonesty({ unreadyReason, withheldRankedCount });
    const withheldBrief = buildLiveWithheldOperatorBrief({
      unreadyReason,
      withheldRankedCount,
      bookHonesty,
    });
    return (
      <div className="imp-opportunity-feed-unready">
        <AttentionBanner
          tone={unready.tone}
          affects={unready.affects}
          action={{ label: "Open Control", href: controlHref(nextAction) }}
        >
          {unready.sentence ?? unready.label}
          {clockHonesty}
          {unreadyReason ? (
            <span className="imp-radar-muted" title="Raw reason code">
              {" "}
              ({unreadyReason})
            </span>
          ) : null}
        </AttentionBanner>
        {withheldBrief ? (
          <section
            className="imp-radar-operator-brief"
            aria-label="Operator questions"
            data-testid="imp-radar-operator-brief"
          >
            <h4 className="imp-radar-subhead">Operator questions</h4>
            <dl className="imp-radar-brief-grid">
              {withheldBrief.map((item) => (
                <div key={item.question} className="imp-radar-brief-row" data-honesty={item.honesty}>
                  <dt>{item.question}</dt>
                  <dd>
                    {item.answer}
                    <span className="imp-radar-brief-honesty">{item.honesty}</span>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}
      </div>
    );
  }

  if (feedStatus === "UNAVAILABLE") {
    if (mode === "LIVE") {
      return (
        <EmptyState
          title="Live has no opportunity engine"
          reason="This is by design, not a feed fault. Use Radar screeners and workspace evidence to investigate instruments. Live execution stays OFF."
        />
      );
    }
    const unavailable = resolveSemanticState("research", "UNAVAILABLE");
    return (
      <EmptyState
        title={unavailable.label}
        reason={unavailable.sentence ?? "The opportunity feed is unavailable."}
        action={{ label: "Open Control", href: controlHref(nextAction) }}
      />
    );
  }

  if (!itemCount) {
    return <EmptyState title="No opportunities right now" reason={emptyReason} />;
  }

  return <>{children}</>;
}
