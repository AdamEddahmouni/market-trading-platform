import type { OpportunityEvidenceResponse, OpportunityReviewRow } from "../../api/opportunityClient";

export const PROGRESSIVE_OPPORTUNITY_COCKPIT_READY = "PROGRESSIVE_OPPORTUNITY_COCKPIT_READY";

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

export const fixtureOpportunityEvidenceVerified: OpportunityEvidenceResponse = {
  ...fixtureOpportunityEvidenceRefresh,
  evidence_class: "VERIFIED",
  items: [
    { kind: "forecast", id: "fc-replay-1" },
    { kind: "agent_enrichment", id: "ae-1" },
  ],
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
