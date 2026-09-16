/**
 * Command decision KPIs (UIR-01D).
 *
 * The Command strip answers operator-orientation questions only — "can I
 * trust the queue?", "is anything actionable?", "does anything need me?",
 * "is the evidence degrading?" — derived from the live opportunities and
 * attention contracts. It is not a portfolio panel (Paper risk/account live
 * in the risk ribbon and page header) and not a StatusBar duplicate (mode,
 * authority, provider, and as-of context stay on the shell).
 *
 * Tones route through the semantic design system (`SemanticTone`); every
 * toned cell pairs color with an icon and text. No vanity metrics: each cell
 * is a count or state the operator can act on.
 */
import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { humanizeEnum, type SemanticTone } from "../../state/semanticState";
import {
  canOpenOpportunityWorkspace,
  humanizeUnreadyReason,
} from "../opportunity/opportunityPresentation";

export type OverviewKpiCell = {
  id: string;
  label: string;
  value: string;
  detail?: string;
  /** Semantic tone — neutral cells render unaccented by design. */
  tone?: SemanticTone;
};

export type OverviewKpiInput = {
  opportunityState: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  opportunityItems: OpportunityReviewRow[];
  attentionState: "loading" | "ready" | "error";
  attentionItems: AttentionItem[];
};

/** Queue-trust cell: the feed status as operator language. */
function queueDataCell(input: OverviewKpiInput): OverviewKpiCell {
  const base = { id: "queue-data", label: "Opportunity feed" };
  if (input.opportunityState === "loading") return { ...base, value: "…", tone: "neutral" };
  if (input.opportunityState === "error") {
    return { ...base, value: "Unavailable", detail: "Feed request failed", tone: "critical" };
  }
  switch (input.feedStatus) {
    case "READY":
      return { ...base, value: "Ready", tone: "live" };
    case "UNREADY": {
      const reason = humanizeUnreadyReason(input.unreadyReason);
      return {
        ...base,
        value: "Not ready",
        detail: reason ? `Queue may be incomplete — ${reason}` : "Queue may be incomplete",
        tone: "caution",
      };
    }
    case "UNAVAILABLE":
      return { ...base, value: "Unavailable", tone: "critical" };
    case "EMPTY":
      return { ...base, value: "Empty", detail: "Nothing minted for current coverage", tone: "neutral" };
    case undefined:
      return { ...base, value: "—", tone: "neutral" };
    default:
      return { ...base, value: humanizeEnum(input.feedStatus ?? ""), tone: "neutral" };
  }
}

/** Actionable cell: rows the operator can lawfully take to a workspace now. */
function actionableCell(input: OverviewKpiInput): OverviewKpiCell {
  const base = { id: "actionable", label: "Actionable now" };
  if (input.opportunityState === "loading") return { ...base, value: "…", tone: "neutral" };
  if (input.opportunityState === "error") return { ...base, value: "—", detail: "Unavailable", tone: "neutral" };
  const total = input.opportunityItems.length;
  const actionable = input.opportunityItems.filter(canOpenOpportunityWorkspace).length;
  return {
    ...base,
    value: String(actionable),
    detail: total ? `of ${total} ranked` : undefined,
    tone: actionable > 0 ? "live" : "neutral",
  };
}

/** Attention cell: signals awaiting review; urgent (tier-1) items call out. */
function attentionCell(input: OverviewKpiInput): OverviewKpiCell {
  const base = { id: "attention", label: "Needs review" };
  if (input.attentionState === "loading") return { ...base, value: "…", tone: "neutral" };
  if (input.attentionState === "error") return { ...base, value: "—", detail: "Unavailable", tone: "neutral" };
  const urgent = input.attentionItems.filter((item) => (item.tier ?? 2) === 1).length;
  return {
    ...base,
    value: String(input.attentionItems.length),
    detail: urgent > 0 ? `${urgent} urgent — act now` : undefined,
    tone: urgent > 0 ? "caution" : "neutral",
  };
}

/** Degradation cell: ranked rows with stale freshness or degraded quality. */
function degradedCell(input: OverviewKpiInput): OverviewKpiCell {
  const base = { id: "degraded", label: "Stale or degraded" };
  if (input.opportunityState === "loading") return { ...base, value: "…", tone: "neutral" };
  if (input.opportunityState === "error") return { ...base, value: "—", detail: "Unavailable", tone: "neutral" };
  const flagged = input.opportunityItems.filter((row) => {
    const quality = row.data_quality;
    if (!quality) return false;
    const status = String(quality.status ?? "").toUpperCase();
    const freshness = String(quality.freshness ?? "").toUpperCase();
    return freshness === "STALE" || status === "DEGRADED" || status === "INVALID";
  }).length;
  return { ...base, value: String(flagged), tone: flagged > 0 ? "caution" : "neutral" };
}

/**
 * The Command decision strip: feed trust, actionable count, attention load,
 * and evidence degradation. Each group degrades independently and honestly —
 * a failed query yields "—"/"Unavailable" cells, never fabricated numbers.
 */
export function overviewDecisionKpis(input: OverviewKpiInput): OverviewKpiCell[] {
  return [queueDataCell(input), actionableCell(input), attentionCell(input), degradedCell(input)];
}
