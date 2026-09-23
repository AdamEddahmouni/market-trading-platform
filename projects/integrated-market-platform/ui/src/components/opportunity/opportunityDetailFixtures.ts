import type { OpportunityEvidenceResponse, OpportunityReviewRow } from "../../api/opportunityClient";

export const OPPORTUNITY_DETAIL_MODEL_READY = "OPPORTUNITY_DETAIL_MODEL_READY";

export const fixtureOpportunityRowBase: OpportunityReviewRow = {
  summary_id: "sum-progressive-1",
  opportunity_id: "opp-progressive-1",
  headline: "BIYA continuation candidate",
  instrument_id: "BIYA",
  instrument_key: "BIYA",
  identity_kind: "OPPORTUNITY_V1",
  eligibility_state: "ELIGIBLE",
  lifecycle_state: "NORMALIZED",
  next_safe_action: "OPEN_WORKSPACE",
  rank_order: 1,
  evidence_class: "CANDIDATE",
  evidence_promotion_reason: "Family admission from replay fixture",
  family_admission_status: "ADMITTED",
  family_admission_reason: "DETERMINISTIC_CHECKS_PASS",
  data_quality: {
    status: "GOOD",
    freshness: "REPLAY",
    source: "REPLAY",
  },
  ranking_vector: {
    basis: "COMPARATOR_LEXICOGRAPHIC",
    dimensions: [{ name: "MOMENTUM", status: "PRESENT", value: 0.42 }],
  },
  decision_support: {
    authority: "DOWNSTREAM_RISK_NOT_RANKING",
    kill_switch: "UNAVAILABLE",
  },
  created_at_ns: 1_700_000_000_000_000_000,
};

export const fixtureOpportunityEvidenceRefresh: OpportunityEvidenceResponse = {
  evidence_class: "CANDIDATE",
  evidence_promotion_reason: "Family admission from replay fixture",
  family_admission_status: "ADMITTED",
  family_admission_reason: "DETERMINISTIC_CHECKS_PASS",
  created_at_ns: 1_700_000_000_000_000_000,
  items: [{ kind: "forecast", id: "fc-replay-1" }],
};

/** Admitted opportunity evidence carrying decision provenance (schema 1.0.0). */
export const fixtureOpportunityDecisionProvenanceEvidence: OpportunityEvidenceResponse = {
  ...fixtureOpportunityEvidenceRefresh,
  invalidation_criteria: ["TREND_BREAK", "SPREAD_TOO_WIDE"],
  actionability_audit: {
    status: "ACTIONABLE",
    still_actionable_reasons: ["LIFECYCLE_ELIGIBLE", "FRESHNESS_FRESH"],
    no_longer_actionable_reasons: [],
    lineage_status: "PRESENT",
  },
  decision_provenance: {
    schema_version: "opportunity/decision_provenance/1.0.0",
    origin_kind: "STRATEGY_MATCH",
    strategy_id: "momentum-5m",
    strategy_family: "momentum",
    thesis: {
      statement: "Momentum continuation after unusual volume",
      honesty: "DERIVED",
      mechanism: "trend_continuation",
      invalidation_criteria: ["SPREAD_TOO_WIDE", "TREND_BREAK"],
    },
    freshness_window: {
      policy_name: "strategy_match_default",
      status: "FRESH",
      valid_until_ns: 1_700_000_300_000_000_000,
      information_cutoff_ns: 1_700_000_000_000_000_000,
    },
    actionability: {
      status: "ACTIONABLE",
      still_actionable_reasons: ["LIFECYCLE_ELIGIBLE", "FRESHNESS_FRESH"],
      no_longer_actionable_reasons: [],
      lineage_status: "PRESENT",
    },
    ai_assisted_notes: ["Model paraphrase of volume spike — not authority"],
    lineage_status: "PRESENT",
  },
};

export const fixtureOpportunityEvidenceVerified: OpportunityEvidenceResponse = {
  ...fixtureOpportunityEvidenceRefresh,
  evidence_class: "VERIFIED",
  items: [
    { kind: "forecast", id: "fc-replay-1" },
    { kind: "agent_enrichment", id: "ae-1" },
  ],
};

/** Replay-only options-flow attachment (matches golden fixture projection; not live feed). */
export const fixtureOpportunityOptionsFlowReplayEvidence: OpportunityEvidenceResponse = {
  ...fixtureOpportunityEvidenceRefresh,
  research_artifact_evidence: {
    authority_class: "EVIDENCE_NOT_PREDICTION",
    readiness: "OPTIONS_FLOW_REPLAY_EVIDENCE_READY",
    attachments: [
      {
        attachment_id: "ofr-nvda-default",
        artifact_type: "OPTIONS_FLOW_REPLAY_EVIDENCE_ARTIFACT",
        content_sha256: "8396D6B3FF31ECE0743F728F5AA2D753133A8F7C689FD566EBCB3C68CC0EF3BF",
        status: "RESOLVED",
        authority_class: "EVIDENCE_NOT_PREDICTION",
        options_flow_transparent_context: {
          authority_class: "EVIDENCE_NOT_PREDICTION",
          artifact_type: "OPTIONS_FLOW_REPLAY_EVIDENCE_ARTIFACT",
          replay_mode: "SYNTHETIC_FIXTURE_ONLY",
          live_feed_claim: "NOT_CLAIMED",
          print_count: 3,
          trade_class_counts: { block: 1, sweep: 2 },
          missing_data_fields_union: ["gex_context.net_gamma_oi_weighted", "quote_age_ms"],
          explicit_exclusions: ["vendor_composite_score", "confirmation_score", "opaque_whale_score"],
          decomposed_prints: [
            {
              print_index: 0,
              option_type: "call",
              strike: 130,
              expiry: "2026-08-15",
              trade_classification: { trade_class: "sweep" },
              quote_age: { available: true, quote_age_ms: 120, staleness: "fresh" },
              aggressor_confidence: { available: true, band: "medium", confidence: 0.81 },
              signed_flow: { direction: "buy_initiated", open_close: "open", quality_flags: [] },
              missing_data_fields: [],
            },
            {
              print_index: 2,
              option_type: "put",
              strike: 125,
              expiry: "2026-08-15",
              trade_classification: { trade_class: "sweep" },
              quote_age: { available: false, reason: "QUOTE_AGE_MISSING" },
              aggressor_confidence: { available: true, band: "low", confidence: 0.62 },
              signed_flow: { direction: "sell_initiated", open_close: "close", quality_flags: [] },
              missing_data_fields: ["quote_age_ms", "gex_context.net_gamma_oi_weighted"],
            },
          ],
        },
      },
    ],
  },
};

export function fixtureRowAfterEvidenceRefresh(): OpportunityReviewRow {
  return {
    ...fixtureOpportunityRowBase,
    evidence_class: "VERIFIED",
    metadata: {
      agent_enrichment: { status: "COMPLETE", count: 1 },
    },
  };
}

/**
 * TEST-ONLY: eligible Paper row whose freshness is STALE.
 * Must remain STALE in presentation — never coerce to FRESH.
 * Eligibility stays ELIGIBLE so Watch/Dismiss gating is orthogonal to freshness.
 */
export const fixtureOpportunityRowStaleEligible: OpportunityReviewRow = {
  ...fixtureOpportunityRowBase,
  summary_id: "sum-stale-eligible-1",
  opportunity_id: "opp-stale-eligible-1",
  headline: "STALE eligible linkage fixture",
  data_quality: {
    status: "DEGRADED",
    freshness: "STALE",
    source: "TEST_ONLY_FIXTURE",
    reason_codes: ["STALE_AFTER_THRESHOLD"],
  },
};

/**
 * TEST-ONLY: non-empty backend provider_linkage_warnings (operator phrases).
 * UI must render these verbatim and must not invent "wrong ticker".
 */
export const fixtureOpportunityRowProviderLinkageWarned: OpportunityReviewRow = {
  ...fixtureOpportunityRowBase,
  summary_id: "sum-linkage-warned-1",
  opportunity_id: "opp-linkage-warned-1",
  instrument_id: "NVDA",
  headline: "MillerKnoll announces new lineup",
  provider_linkage_warnings: ["uncorroborated", "contextual concern", "low confidence"],
};
