import { describe, expect, it } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { radarAckResult, radarOpportunityActions, type RadarActionContext } from "./radarOperatorActions";

function row(overrides: Partial<OpportunityReviewRow> = {}): OpportunityReviewRow {
  return {
    summary_id: "sum-1",
    opportunity_id: "opp-1",
    instrument_id: "BIYA",
    headline: "BIYA momentum ignition watch",
    identity_kind: "OPPORTUNITY_V1",
    eligibility_state: "ELIGIBLE",
    lifecycle_state: "ACTIVE",
    next_safe_action: "OPEN_WORKSPACE",
    ...overrides,
  };
}

function ctx(overrides: Partial<RadarActionContext> = {}): RadarActionContext {
  return {
    row: row(),
    sourceState: "ready",
    readOnly: false,
    paperActions: true,
    paperAccountId: "paper-acct-1",
    surface: "detail",
    ...overrides,
  };
}

describe("radar operator actions", () => {
  it("offers review, watch, dismiss, and workspace without confirmation when the row is actionable", () => {
    const actions = radarOpportunityActions(ctx());
    expect(actions.review.availability).toBe("AVAILABLE");
    expect(actions.watch.availability).toBe("AVAILABLE");
    expect(actions.dismiss.availability).toBe("AVAILABLE");
    expect(actions.openWorkspace.availability).toBe("AVAILABLE");
    expect(actions.review.confirmation).toBeUndefined();
    expect(actions.watch.confirmation).toBeUndefined();
    expect(actions.dismiss.confirmation).toBeUndefined();
    expect(actions.openWorkspace.confirmation).toBeUndefined();
    expect(actions.review.consequence).toBe("operator_record");
    expect(actions.openWorkspace.consequence).toBe("navigation");
    expect(actions.openWorkspace.domain).toBe("radar.handoff");
    expect(actions.watch.target).toEqual({ label: "BIYA", id: "opp-1" });
  });

  it("stays unavailable when the feed or row is missing", () => {
    expect(radarOpportunityActions(ctx({ sourceState: "loading" })).watch.availability).toBe("UNAVAILABLE");
    expect(radarOpportunityActions(ctx({ sourceState: "loading" })).watch.reason?.code).toBe("RADAR_FEED_LOADING");
    expect(radarOpportunityActions(ctx({ sourceState: "failed", row: null })).dismiss.reason?.code).toBe(
      "RADAR_FEED_UNAVAILABLE",
    );
    expect(radarOpportunityActions(ctx({ row: null })).review.reason?.code).toBe("OPPORTUNITY_STATE_UNAVAILABLE");
  });

  it("blocks expired, superseded, ineligible, and unknown eligibility without treating them as healthy", () => {
    expect(radarOpportunityActions(ctx({ row: row({ lifecycle_state: "EXPIRED" }) })).watch.reason?.code).toBe(
      "OPPORTUNITY_EXPIRED",
    );
    expect(
      radarOpportunityActions(ctx({ row: row({ supersession_reason: "newer-print" }) })).dismiss.reason?.code,
    ).toBe("OPPORTUNITY_SUPERSEDED");
    expect(
      radarOpportunityActions(
        ctx({ row: row({ eligibility_state: "INELIGIBLE", next_safe_action: "STOP" }) }),
      ).review.reason?.code,
    ).toBe("OPPORTUNITY_INELIGIBLE");
    expect(radarOpportunityActions(ctx({ row: row({ eligibility_state: "UNAVAILABLE" }) })).watch.availability).toBe(
      "UNAVAILABLE",
    );
    expect(radarOpportunityActions(ctx({ row: row({ eligibility_state: undefined }) })).watch.reason?.code).toBe(
      "ELIGIBILITY_UNKNOWN",
    );
  });

  it("blocks a repeated watch, review, or dismiss from the stored lifecycle", () => {
    expect(radarOpportunityActions(ctx({ row: row({ lifecycle_state: "WATCHED" }) })).watch.reason?.code).toBe(
      "ALREADY_WATCHED",
    );
    expect(radarOpportunityActions(ctx({ row: row({ lifecycle_state: "WATCHED" }) })).dismiss.availability).toBe(
      "AVAILABLE",
    );
    expect(radarOpportunityActions(ctx({ row: row({ lifecycle_state: "REVIEWED" }) })).review.reason?.code).toBe(
      "ALREADY_REVIEWED",
    );
    expect(radarOpportunityActions(ctx({ row: row({ lifecycle_state: "DISMISSED" }) })).watch.reason?.code).toBe(
      "ALREADY_DISMISSED",
    );
  });

  it("uses read-only and unavailable mode reasons without inventing execution authority", () => {
    const readOnly = radarOpportunityActions(ctx({ readOnly: true }));
    expect(readOnly.watch.availability).toBe("READ_ONLY");
    expect(readOnly.watch.reason?.detail).toMatch(/Read-only in this mode/);
    expect(readOnly.openWorkspace.availability).toBe("AVAILABLE");
    const noPaper = radarOpportunityActions(ctx({ paperActions: false }));
    expect(noPaper.dismiss.availability).toBe("UNAVAILABLE");
    expect(noPaper.dismiss.reason?.detail).toMatch(/Paper actions unavailable/);
    const noAccount = radarOpportunityActions(ctx({ paperAccountId: null }));
    expect(noAccount.review.reason?.code).toBe("PAPER_ACCOUNT_UNAVAILABLE");
  });

  it("allows investigation even when execution review is blocked, but requires an instrument", () => {
    expect(
      radarOpportunityActions(ctx({ row: row({ instrument_id: null }) })).openWorkspace.reason?.code,
    ).toBe("WORKSPACE_INSTRUMENT_MISSING");
    expect(
      radarOpportunityActions(ctx({ row: row({ next_safe_action: "EXPLAIN" }) })).openWorkspace.availability,
    ).toBe("AVAILABLE");
  });

  it("maps ack failure and failed reconciliation onto shared result kinds", () => {
    expect(radarAckResult("failed")?.kind).toBe("REQUEST_FAILED");
    expect(radarAckResult("reconciliation_failed", "tr-1")?.kind).toBe("REFRESH_FAILED_AFTER_MUTATION");
    expect(radarAckResult("reconciliation_failed", "tr-1")?.message).toMatch(/tr-1/);
    expect(radarAckResult("completed")?.kind).toBe("SUCCESS");
    expect(radarAckResult("idle")).toBeNull();
    expect(radarAckResult("submitting")).toBeNull();
  });
});
