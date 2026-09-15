import { describe, expect, it } from "vitest";
import {
  assertStableIdentityAcrossEvidenceRefresh,
  buildProgressiveOpportunitySections,
  derivePresentationState,
} from "./progressiveOpportunityModel";
import {
  fixtureOpportunityEvidenceRefresh,
  fixtureOpportunityEvidenceVerified,
  fixtureOpportunityRowBase,
  fixtureRowAfterEvidenceRefresh,
  PROGRESSIVE_OPPORTUNITY_COCKPIT_READY,
} from "./progressiveOpportunityFixtures";

describe(PROGRESSIVE_OPPORTUNITY_COCKPIT_READY, () => {
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
    const sections = buildProgressiveOpportunitySections(fixtureOpportunityRowBase, {
      evidence: fixtureOpportunityEvidenceRefresh,
    });
    expect(sections.historicalContext.status).toBe("UNAVAILABLE");
    expect(sections.historicalContext.lines[0]).toMatch(/not linked/i);
    const serialized = JSON.stringify(sections);
    expect(serialized).not.toMatch(/probability/i);
    expect(serialized).not.toMatch(/%/);
  });

  it("separates visibility from actionability when gates fail", () => {
    const blocked = buildProgressiveOpportunitySections(
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
