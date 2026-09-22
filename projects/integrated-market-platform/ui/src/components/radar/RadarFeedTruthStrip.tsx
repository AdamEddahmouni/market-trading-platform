import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { StatePill } from "../imp-ui/StatePill";
import type { OperatorBriefFeedContext } from "../opportunity/opportunityOperatorBrief";
import { humanizeEnum, type SemanticTone } from "../../state/semanticState";

export type RadarFeedTruthStripProps = {
  feedStatus?: string;
  itemCount: number;
  feed?: OperatorBriefFeedContext | null;
  qualityState?: string;
};

type TruthClass = {
  label: string;
  tone: SemanticTone;
  raw: string;
  /** True when this surface must not be read as live/current market time. */
  nonCurrent: boolean;
};

/**
 * Map backend as-of / data_mode into an operator-visible truth class.
 * Replay and simulation never render as "Current".
 */
export function resolveFeedTruthClass(feed?: OperatorBriefFeedContext | null): TruthClass {
  const mode = String(feed?.mode ?? "").toUpperCase();
  const dataMode = String(feed?.data_mode ?? "").toUpperCase();

  if (mode === "REPLAY" || dataMode === "FIXTURE_REPLAY" || dataMode === "HISTORICAL_CAPTURE") {
    return {
      label: "Replay — not live market time",
      tone: "replay",
      raw: dataMode || mode || "REPLAY",
      nonCurrent: true,
    };
  }
  if (mode === "SIMULATION") {
    return {
      label: "Simulation — not live market time",
      tone: "replay",
      raw: mode,
      nonCurrent: true,
    };
  }
  if (dataMode === "BROKER_DELAYED") {
    return {
      label: "Delayed quotes",
      tone: "caution",
      raw: dataMode,
      nonCurrent: false,
    };
  }
  if (mode === "LIVE" || dataMode === "LIVE_OBSERVATIONAL") {
    return {
      label: "Current observational feed",
      tone: "live",
      raw: dataMode || mode || "LIVE",
      nonCurrent: false,
    };
  }
  if (mode === "PAPER") {
    return {
      label: "Paper session context",
      tone: "paper",
      raw: mode,
      nonCurrent: false,
    };
  }
  return {
    label: "Feed context unavailable",
    tone: "neutral",
    raw: "UNAVAILABLE",
    nonCurrent: true,
  };
}

function feedStatusTone(status?: string): SemanticTone {
  const upper = String(status ?? "").toUpperCase();
  if (upper === "READY") return "live";
  if (upper === "UNREADY" || upper === "DEGRADED") return "caution";
  if (upper === "UNAVAILABLE" || upper === "ERROR") return "critical";
  if (upper === "EMPTY") return "neutral";
  return "neutral";
}

/**
 * Compact feed truth strip for the Opportunities tab: current vs replay vs
 * unavailable, item count, and as-of provenance. Backend tokens stay in the
 * pill `raw` attribute; primary copy is human.
 */
export function RadarFeedTruthStrip({
  feedStatus,
  itemCount,
  feed = null,
  qualityState,
}: RadarFeedTruthStripProps) {
  const truth = resolveFeedTruthClass(feed);
  const statusLabel = feedStatus ? humanizeEnum(feedStatus) : "Unknown";
  const quality = qualityState ? humanizeEnum(qualityState) : null;

  return (
    <aside
      className="imp-radar-feed-truth"
      data-testid="imp-radar-feed-truth"
      data-non-current={truth.nonCurrent ? "true" : "false"}
      aria-label="Opportunity feed truth"
    >
      <div className="imp-radar-feed-truth-pills">
        <StatePill
          tone={feedStatusTone(feedStatus)}
          label={statusLabel}
          raw={feedStatus ?? "UNKNOWN"}
          size="sm"
        />
        <StatePill tone={truth.tone} label={truth.label} raw={truth.raw} size="sm" />
        {quality ? (
          <StatePill
            tone={String(qualityState).toUpperCase() === "STALE" ? "caution" : "neutral"}
            label={`Quality ${quality}`}
            raw={qualityState}
            size="sm"
          />
        ) : null}
      </div>
      <p className="imp-radar-feed-truth-copy">
        <span>
          {itemCount} ranked {itemCount === 1 ? "opportunity" : "opportunities"}
        </span>
        {feed?.data_provider ? (
          <span>
            {" "}
            · Source <code>{feed.data_provider}</code>
          </span>
        ) : (
          <span> · Source unavailable</span>
        )}
        {feed?.as_of_provenance ? (
          <span>
            {" "}
            · Provenance <code>{feed.as_of_provenance}</code>
          </span>
        ) : null}
      </p>
      <div className="imp-radar-feed-truth-fresh">
        <FreshnessIndicator asOf={feed?.as_of_time ?? null} decays={!truth.nonCurrent} />
        {truth.nonCurrent ? (
          <span className="imp-radar-muted">Replay must not be read as current.</span>
        ) : null}
      </div>
      <p className="imp-radar-feed-truth-hint imp-radar-muted">
        Keyboard: ↑/↓ or j/k select · w watch · d dismiss · Enter opens detail on narrow layouts.
      </p>
    </aside>
  );
}
