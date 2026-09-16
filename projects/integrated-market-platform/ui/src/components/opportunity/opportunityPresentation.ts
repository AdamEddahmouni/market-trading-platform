/**
 * Shared opportunity presentation primitives (UIR-01C).
 *
 * ONE opportunity language across Radar, Command, and Paper surfaces: the
 * same backend state resolves to the same label/tone everywhere. Page context
 * changes layout, never semantic meaning. All values translate backend fields
 * only — the UI never invents operational state (see state/semanticState.ts).
 */
import type { AttentionItem } from "../../api/client";
import type {
  OpportunityEvidenceResponse,
  OpportunityReviewRow,
} from "../../api/opportunityClient";
import { resolveSemanticState, type SemanticState, type SemanticTone } from "../../state/semanticState";

/** Presentation lifecycle derived from backend fields (never stored). */
export type OpportunityPresentationState =
  | "DETECTED"
  | "PROVISIONAL"
  | "VERIFYING"
  | "VERIFIED"
  | "CONTRADICTED"
  | "EXPIRED";

export const OPPORTUNITY_STATE_LABEL: Record<OpportunityPresentationState, string> = {
  DETECTED: "Detected",
  PROVISIONAL: "Provisional",
  VERIFYING: "Verifying",
  VERIFIED: "Verified",
  CONTRADICTED: "Contradicted",
  EXPIRED: "Expired",
};

export const OPPORTUNITY_STATE_TONE: Record<OpportunityPresentationState, SemanticTone> = {
  DETECTED: "neutral",
  PROVISIONAL: "caution",
  VERIFYING: "research",
  VERIFIED: "live",
  CONTRADICTED: "critical",
  EXPIRED: "neutral",
};

/** Stable identity key: evidence refreshes must not change it. */
export function stableOpportunityKey(row: OpportunityReviewRow): string {
  return row.opportunity_id ?? row.summary_id;
}

export function explanationRefForRow(row: OpportunityReviewRow): string {
  if (row.explanation_ref) return row.explanation_ref;
  if (row.opportunity_id) return `explain:opportunity:${row.opportunity_id}`;
  return `explain:summary:${row.summary_id}`;
}

/** Bridge from an opportunity row to the shell's attention-item channels. */
export function attentionItemFromOpportunity(row: OpportunityReviewRow): AttentionItem {
  return {
    attention_id: row.summary_id,
    priority_rank: row.rank_order ?? 0,
    headline: row.headline,
    instrument_id: row.instrument_id ?? undefined,
    explanation_ref: explanationRefForRow(row),
    reasons: [],
  };
}

export function opportunityRankLabel(row: OpportunityReviewRow): string | null {
  if (row.rank_order == null) return null;
  return `#${row.rank_order}`;
}

export function opportunitySymbol(row: OpportunityReviewRow): string {
  if (row.instrument_id?.trim()) return row.instrument_id.trim();
  return "—";
}

function agentEnrichmentStatus(row: OpportunityReviewRow): string {
  const metadata = row.metadata;
  if (!metadata || typeof metadata !== "object") return "";
  const agent = (metadata as Record<string, unknown>).agent_enrichment;
  if (!agent || typeof agent !== "object") return "";
  return String((agent as Record<string, unknown>).status ?? "").toUpperCase();
}

/**
 * Derive the presentation state from backend lifecycle/evidence fields.
 * Ordering matters: expiry and contradiction outrank verification.
 */
export function derivePresentationState(
  row: OpportunityReviewRow,
  evidence?: OpportunityEvidenceResponse | null,
): OpportunityPresentationState {
  const lifecycle = String(row.lifecycle_state ?? "").toUpperCase();
  if (lifecycle.includes("EXPIRED")) return "EXPIRED";

  const evidenceClass = String(evidence?.evidence_class ?? row.evidence_class ?? "").toUpperCase();
  const supersession = evidence?.supersession_reason ?? row.supersession_reason;
  const hasSupersession = supersession != null && supersession !== "";
  const duplicates = evidence?.duplicates?.length ?? (Array.isArray(row.duplicates) ? row.duplicates.length : 0);
  const agentStatus = agentEnrichmentStatus(row);

  if (hasSupersession || duplicates > 0 || agentStatus === "CONTRADICTED") {
    return "CONTRADICTED";
  }
  if (evidenceClass.includes("VERIFIED")) return "VERIFIED";
  if (agentStatus === "PENDING" || agentStatus === "INGESTING") return "VERIFYING";

  const basis = row.ranking_vector?.basis;
  const provisional =
    row.identity_kind !== "OPPORTUNITY_V1" || Boolean(basis && basis !== "COMPARATOR_LEXICOGRAPHIC");
  if (provisional) return "PROVISIONAL";
  return "DETECTED";
}

/** Ranking-input coverage, e.g. "2/3 inputs" — evidence strength, not a score. */
export function evidenceInputsSummary(row: OpportunityReviewRow): string {
  const dimensions = row.ranking_vector?.dimensions ?? [];
  if (!dimensions.length) return "—";
  const present = dimensions.filter((d) => d.status === "PRESENT").length;
  return `${present}/${dimensions.length} inputs`;
}

/** Long-form variant for detail surfaces, e.g. "2 of 3 ranking inputs present". */
export function evidenceInputsSentence(row: OpportunityReviewRow): string {
  const dimensions = row.ranking_vector?.dimensions ?? [];
  if (!dimensions.length) return "Ranking inputs unavailable";
  const present = dimensions.filter((d) => d.status === "PRESENT").length;
  return `${present} of ${dimensions.length} ranking inputs present`;
}

/** Eligibility gate: STOP / INELIGIBLE means do not act, regardless of page. */
export function isOpportunityIneligible(row: OpportunityReviewRow): boolean {
  return row.eligibility_state === "INELIGIBLE" || row.next_safe_action === "STOP";
}

/** Workspace preview is offered only for instrument-backed, eligible rows. */
export function canOpenOpportunityWorkspace(row: OpportunityReviewRow): boolean {
  return Boolean(
    row.instrument_id && row.next_safe_action === "OPEN_WORKSPACE" && !isOpportunityIneligible(row),
  );
}

/** Ack (watch/review/dismiss) is never offered for stopped/ineligible rows. */
export function canAckOpportunity(row: OpportunityReviewRow): boolean {
  return !isOpportunityIneligible(row);
}

/** The one next-safe-action resolution: STOP wins, then the backend action. */
export function opportunityNextActionState(row: OpportunityReviewRow): SemanticState {
  return resolveSemanticState(
    "research",
    isOpportunityIneligible(row) ? "STOP" : row.next_safe_action,
  );
}

/** Provisional ranking order (not FTEP-tuned / campaign-calibrated). */
export function hasProvisionalOrder(row: OpportunityReviewRow): boolean {
  const basis = row.ranking_vector?.basis;
  return Boolean(basis && basis !== "COMPARATOR_LEXICOGRAPHIC");
}
