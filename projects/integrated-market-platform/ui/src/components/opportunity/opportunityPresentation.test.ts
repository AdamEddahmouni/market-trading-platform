import { describe, expect, it } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import {
  attentionItemFromOpportunity,
  attentionOpportunityLinks,
  canAckOpportunity,
  canOpenOpportunityWorkspace,
  derivePresentationState,
  evidenceInputsSentence,
  evidenceInputsSummary,
  explanationRefForRow,
  hasProvisionalOrder,
  humanizeUnreadyReason,
  isOpportunityIneligible,
  opportunityNextActionState,
  stableOpportunityKey,
} from "./opportunityPresentation";

function row(overrides: Partial<OpportunityReviewRow> = {}): OpportunityReviewRow {
  return {
    summary_id: "sum-1",
    opportunity_id: "opp-1",
    headline: "BIYA momentum ignition watch",
    instrument_id: "BIYA",
    identity_kind: "OPPORTUNITY_V1",
    eligibility_state: "ELIGIBLE",
    lifecycle_state: "ACTIVE",
    next_safe_action: "OPEN_WORKSPACE",
    rank_order: 1,
    ranking_vector: {
      basis: "COMPARATOR_LEXICOGRAPHIC",
      dimensions: [
        { name: "attention_score", status: "PRESENT", value: 74.5 },
        { name: "freshness", status: "PRESENT", value: "FRESH" },
        { name: "liquidity", status: "MISSING" },
      ],
      rank_order: 1,
    },
    data_quality: { status: "PASS", freshness: "FRESH", source: "unit-test" },
    ...overrides,
  };
}

describe("opportunityPresentation", () => {
  it("keeps a stable identity key from opportunity_id, falling back to summary_id", () => {
    expect(stableOpportunityKey(row())).toBe("opp-1");
    expect(stableOpportunityKey(row({ opportunity_id: null }))).toBe("sum-1");
  });

  it("builds explanation refs without inventing identifiers", () => {
    expect(explanationRefForRow(row())).toBe("explain:opportunity:opp-1");
    expect(explanationRefForRow(row({ explanation_ref: "explain:custom:1" }))).toBe("explain:custom:1");
    expect(explanationRefForRow(row({ opportunity_id: null }))).toBe("explain:summary:sum-1");
    expect(attentionItemFromOpportunity(row()).explanation_ref).toBe("explain:opportunity:opp-1");
  });

  it("derives presentation states from backend fields only", () => {
    expect(derivePresentationState(row())).toBe("DETECTED");
    expect(derivePresentationState(row({ lifecycle_state: "EXPIRED" }))).toBe("EXPIRED");
    expect(derivePresentationState(row({ evidence_class: "VERIFIED" }))).toBe("VERIFIED");
    expect(derivePresentationState(row({ supersession_reason: "REPLACED_BY_NEWER" }))).toBe("CONTRADICTED");
    expect(derivePresentationState(row({ identity_kind: "NOT_OPPORTUNITY_V1" }))).toBe("PROVISIONAL");
    expect(
      derivePresentationState(row({ metadata: { agent_enrichment: { status: "PENDING" } } })),
    ).toBe("VERIFYING");
    expect(
      derivePresentationState(row({ metadata: { agent_enrichment: { status: "CONTRADICTED" } } })),
    ).toBe("CONTRADICTED");
  });

  it("summarizes evidence as input coverage, never a score", () => {
    expect(evidenceInputsSummary(row())).toBe("2/3 inputs");
    expect(evidenceInputsSentence(row())).toBe("2 of 3 ranking inputs present");
    expect(evidenceInputsSummary(row({ ranking_vector: null }))).toBe("—");
    expect(evidenceInputsSentence(row({ ranking_vector: null }))).toBe("Ranking inputs unavailable");
  });

  it("treats STOP, INELIGIBLE, and UNAVAILABLE as do-not-act on every surface", () => {
    const stopped = row({ next_safe_action: "STOP" });
    const ineligible = row({ eligibility_state: "INELIGIBLE" });
    const unavailable = row({ eligibility_state: "UNAVAILABLE", next_safe_action: "OPEN_WORKSPACE" });
    for (const gated of [stopped, ineligible, unavailable]) {
      expect(isOpportunityIneligible(gated)).toBe(true);
      expect(canOpenOpportunityWorkspace(gated)).toBe(false);
      expect(canAckOpportunity(gated)).toBe(false);
      expect(opportunityNextActionState(gated).raw).toBe("STOP");
      expect(opportunityNextActionState(gated).tone).toBe("critical");
    }
  });

  it("offers workspace preview only for instrument-backed eligible rows", () => {
    expect(canOpenOpportunityWorkspace(row())).toBe(true);
    expect(canOpenOpportunityWorkspace(row({ instrument_id: null }))).toBe(false);
    expect(canOpenOpportunityWorkspace(row({ next_safe_action: "NONE" }))).toBe(false);
    expect(opportunityNextActionState(row()).label).toBe("Open workspace");
  });

  it("flags provisional ranking order from the ranking basis", () => {
    expect(hasProvisionalOrder(row())).toBe(false);
    expect(
      hasProvisionalOrder(
        row({ ranking_vector: { basis: "ATTENTION_ORDER", dimensions: [], rank_order: 1 } }),
      ),
    ).toBe(true);
  });

  it("bridges attention signals to ranked rows by exact summary-id identity", () => {
    const links = attentionOpportunityLinks([
      row(),
      row({
        summary_id: "att-strategy-42",
        opportunity_id: null,
        identity_kind: "NOT_OPPORTUNITY_V1",
        rank_order: 2,
      }),
    ]);
    const bridged = links.get("att-strategy-42");
    expect(bridged).toMatchObject({
      summaryId: "att-strategy-42",
      rank: "#2",
      stateLabel: "Provisional",
      stateTone: "caution",
      evidence: "2/3 inputs",
    });
    // Engine rows key on opportunity ids, never attention ids.
    expect(links.get("sum-1")?.summaryId).toBe("sum-1");
    expect(links.get("att-missing")).toBeUndefined();
  });

  it("humanizes known feed-unready reasons and falls back without raw SNAKE_CASE", () => {
    expect(humanizeUnreadyReason("QUALITY_SUMMARY_NOT_HEALTHY")).toBe(
      "market data quality is degraded",
    );
    expect(humanizeUnreadyReason("LIVE_AS_OF_UNAVAILABLE")).toBe("the live clock is unavailable");
    expect(humanizeUnreadyReason("PROVIDER_WARMUP")).toBe("Provider warmup");
    expect(humanizeUnreadyReason(undefined)).toBeNull();
    expect(humanizeUnreadyReason("")).toBeNull();
  });
});
