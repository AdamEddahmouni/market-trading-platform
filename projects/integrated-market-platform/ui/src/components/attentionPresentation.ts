/**
 * Shared attention-signal presentation primitives (UIR-01D).
 *
 * ONE attention language across Command Overview, the Signals desk, and the
 * Paper candidate queue: tier urgency, why-now derivation, and the
 * signal→opportunity bridge shape. All values translate backend fields only —
 * the UI never invents signal state (see state/semanticState.ts).
 *
 * This module deliberately stays free of the opportunity client: the bridge
 * record is a plain presentation shape, and the correlation builder lives in
 * `opportunity/opportunityPresentation.ts` (which owns the row contract).
 */
import type { AttentionItem } from "../api/client";
import type { SemanticTone } from "../state/semanticState";

/** Presentation of one attention tier: text + tone, never color alone. */
export type AttentionTierState = {
  tone: SemanticTone;
  label: string;
  /** Raw backend value, preserved for L4 detail surfaces. */
  raw: string;
};

const TIER_PRESENTATION: Record<number, { tone: SemanticTone; label: string }> = {
  1: { tone: "caution", label: "Tier 1 — act now" },
  2: { tone: "neutral", label: "Tier 2 — review" },
  3: { tone: "neutral", label: "Tier 3 — monitor" },
};

/**
 * Tier urgency. Tier 1 requires operator action (caution: impaired until
 * reviewed — not a system failure); tiers 2/3 are informational. Unknown
 * tiers render neutral with the raw value preserved.
 */
export function attentionTierState(tier: number | undefined): AttentionTierState {
  const value = tier ?? 2;
  const known = TIER_PRESENTATION[value];
  if (known) return { tone: known.tone, label: known.label, raw: `TIER_${value}` };
  return { tone: "neutral", label: `Tier ${value}`, raw: `TIER_${value}` };
}

/**
 * The operator-facing "why now": the signal's reason labels in backend order,
 * deduplicated. Reason labels are already human language from the backend;
 * raw codes stay in the card's detail disclosure. Returns null when the
 * contract carries no reasons — the card then shows no why-now block rather
 * than a synthesized explanation.
 */
export function attentionWhyNow(item: AttentionItem): string | null {
  const labels = item.reasons.map((reason) => reason.label.trim()).filter(Boolean);
  const distinct = [...new Set(labels)];
  return distinct.length ? distinct.join("; ") : null;
}

/**
 * The signal→opportunity bridge record. Built by
 * `attentionOpportunityLinks` from ranked queue rows; keyed by attention id.
 * A present link means the signal is also ranked in the opportunity queue —
 * the only relationship the backend contract supports (the ingest adapter
 * sets `summary_id = attention_id`). Absence means no ranked row exists and
 * the UI must not imply one.
 */
export type AttentionOpportunityLink = {
  /** Ranked-row summary id — also the Radar deep-link selection key. */
  summaryId: string;
  /** "#2" rank label, or null when the row is unranked. */
  rank: string | null;
  /** Shared opportunity presentation-state label/tone (Detected, Verifying, …). */
  stateLabel: string;
  stateTone: SemanticTone;
  /** Ranking-input coverage, e.g. "2/3 inputs" — evidence strength, not a score. */
  evidence: string;
};
