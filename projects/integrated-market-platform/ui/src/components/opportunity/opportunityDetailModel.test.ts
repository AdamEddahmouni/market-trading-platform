import { describe, expect, it } from "vitest";
import {
  assertStableIdentityAcrossEvidenceRefresh,
  buildOpportunityDetailSections,
} from "./opportunityDetailModel";
import { derivePresentationState } from "./opportunityPresentation";
import {
  fixtureOpportunityEvidenceRefresh,
  fixtureOpportunityEvidenceVerified,
  fixtureOpportunityOptionsFlowReplayEvidence,
  fixtureOpportunityRowBase,
  fixtureRowAfterEvidenceRefresh,
  OPPORTUNITY_DETAIL_MODEL_READY,
} from "./opportunityDetailFixtures";

describe(OPPORTUNITY_DETAIL_MODEL_READY, () => {
  it("keeps stable opportunity identity when evidence refreshes without summary drift", () => {
    const before = fixtureOpportunityRowBase;
    const after = fixtureRowAfterEvidenceRefresh();
    assertStableIdentityAcrossEvidenceRefresh(before, after);
    expect(before.summary_id).toBe(after.summary_id);
    expect(before.opportunity_id).toBe(after.opportunity_id);
  });

  it("moves presentation state from DETECTED toward VERIFIED without inventing probabilities", () => {
    const detected = derivePresentationState(fixtureOpportunityRowBase, fixtureOpportunityEvidenceRefresh);
    const verified = derivePresentationState(fixtureRowAfterEvidenceRefresh(), fixtureOpportunityEvidenceVerified);
    expect(detected).toBe("DETECTED");
    expect(verified).toBe("VERIFIED");
  });

  it("surfaces honest UNAVAILABLE historical context when no artifact is linked", () => {
    const sections = buildOpportunityDetailSections(fixtureOpportunityRowBase, {
      evidence: fixtureOpportunityEvidenceRefresh,
    });
    expect(sections.historicalContext.status).toBe("UNAVAILABLE");
    expect(sections.historicalContext.lines[0]).toMatch(/not attached/i);
    const serialized = JSON.stringify(sections);
    expect(serialized).not.toMatch(/probability/i);
    expect(serialized).not.toMatch(/%/);
  });

  it("surfaces replay options-flow evidence without live feed or rank scores", () => {
    const sections = buildOpportunityDetailSections(fixtureOpportunityRowBase, {
      evidence: fixtureOpportunityOptionsFlowReplayEvidence,
    });
    expect(sections.historicalContext.status).toBe("PARTIAL");
    const blob = sections.historicalContext.lines.join("\n");
    expect(blob).toMatch(/OPTIONS_FLOW_REPLAY_EVIDENCE_READY/);
    expect(blob).toMatch(/NOT_CLAIMED/);
    expect(blob).toMatch(/SYNTHETIC_FIXTURE_ONLY/);
    expect(blob).toMatch(/quote age 120 ms/);
    expect(blob).toMatch(/QUOTE_AGE_MISSING/);
    expect(blob).toMatch(/aggressor medium/);
    expect(blob).toMatch(/missing quote_age_ms/);
    expect(blob).toMatch(/Excluded vendor scores/);
    expect(blob).not.toMatch(/rank_score/i);
    expect(blob).not.toMatch(/probability/i);
  });

  it("separates visibility from actionability when gates fail", () => {
    const blocked = buildOpportunityDetailSections(
      {
        ...fixtureOpportunityRowBase,
        eligibility_state: "INELIGIBLE",
        next_safe_action: "STOP",
      },
      { evidence: fixtureOpportunityEvidenceRefresh },
    );
    expect(blocked.actionReadiness.canPreviewWorkspace).toBe(false);
    expect(blocked.actionReadiness.nextSafeAction).toBe("STOP");
    expect(blocked.presentationState).not.toBe("EXPIRED");
  });
});
