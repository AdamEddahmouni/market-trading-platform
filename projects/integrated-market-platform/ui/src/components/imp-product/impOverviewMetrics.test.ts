import { describe, expect, it } from "vitest";
import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { overviewDecisionKpis, type OverviewKpiInput } from "./impOverviewMetrics";

function row(overrides: Partial<OpportunityReviewRow> = {}): OpportunityReviewRow {
  return {
    summary_id: "sum-1",
    headline: "BIYA momentum ignition watch",
    instrument_id: "BIYA",
    identity_kind: "OPPORTUNITY_V1",
    eligibility_state: "ELIGIBLE",
    next_safe_action: "OPEN_WORKSPACE",
    rank_order: 1,
    data_quality: { status: "PASS", freshness: "FRESH" },
    ...overrides,
  };
}

function signal(overrides: Partial<AttentionItem> = {}): AttentionItem {
  return {
    attention_id: "att-1",
    priority_rank: 1,
    headline: "Signal",
    explanation_ref: "explain:att:1",
    reasons: [],
    ...overrides,
  };
}

function input(overrides: Partial<OverviewKpiInput> = {}): OverviewKpiInput {
  return {
    opportunityState: "ready",
    feedStatus: "READY",
    opportunityItems: [],
    attentionState: "ready",
    attentionItems: [],
    ...overrides,
  };
}

describe("overviewDecisionKpis", () => {
  it("answers the four orientation questions from real contract fields", () => {
    const cells = overviewDecisionKpis(
      input({
        opportunityItems: [
          row(),
          row({ summary_id: "sum-2", next_safe_action: "STOP", eligibility_state: "INELIGIBLE" }),
          row({ summary_id: "sum-3", data_quality: { status: "DEGRADED", freshness: "STALE" } }),
        ],
        attentionItems: [signal(), signal({ attention_id: "att-2", tier: 1 })],
      }),
    );
    const byId = new Map(cells.map((cell) => [cell.id, cell]));
    expect(byId.get("queue-data")).toMatchObject({ value: "Ready", tone: "live" });
    // STOP/INELIGIBLE rows are never actionable; the DEGRADED row still is.
    expect(byId.get("actionable")).toMatchObject({ value: "2", detail: "of 3 ranked", tone: "live" });
    expect(byId.get("attention")).toMatchObject({
      value: "2",
      detail: "1 urgent — act now",
      tone: "caution",
    });
    expect(byId.get("degraded")).toMatchObject({ value: "1", tone: "caution" });
  });

  it("marks the feed cell from the backend feed status with humanized reasons", () => {
    const unready = overviewDecisionKpis(
      input({ feedStatus: "UNREADY", unreadyReason: "QUALITY_SUMMARY_NOT_HEALTHY" }),
    );
    expect(unready[0]).toMatchObject({ value: "Not ready", tone: "caution" });
    expect(unready[0].detail).toContain("market data quality is degraded");
    expect(unready[0].detail).not.toContain("QUALITY_SUMMARY_NOT_HEALTHY");

    expect(overviewDecisionKpis(input({ feedStatus: "UNAVAILABLE" }))[0]).toMatchObject({
      value: "Unavailable",
      tone: "critical",
    });
    expect(overviewDecisionKpis(input({ feedStatus: "EMPTY" }))[0]).toMatchObject({
      value: "Empty",
      tone: "neutral",
    });
  });

  it("degrades each query group honestly without fabricating counts", () => {
    const cells = overviewDecisionKpis(
      input({ opportunityState: "error", attentionState: "loading", feedStatus: undefined }),
    );
    const byId = new Map(cells.map((cell) => [cell.id, cell]));
    expect(byId.get("queue-data")).toMatchObject({ value: "Unavailable", tone: "critical" });
    expect(byId.get("actionable")?.value).toBe("—");
    expect(byId.get("attention")?.value).toBe("…");
    expect(byId.get("degraded")?.value).toBe("—");
  });

  it("stays neutral when nothing is actionable, urgent, or degraded", () => {
    const cells = overviewDecisionKpis(input());
    const byId = new Map(cells.map((cell) => [cell.id, cell]));
    expect(byId.get("actionable")).toMatchObject({ value: "0", tone: "neutral" });
    expect(byId.get("attention")).toMatchObject({ value: "0", tone: "neutral" });
    expect(byId.get("degraded")).toMatchObject({ value: "0", tone: "neutral" });
  });

  it("does not count replay-honesty UNAVAILABLE freshness as degradation", () => {
    const cells = overviewDecisionKpis(
      input({
        opportunityItems: [
          row({ data_quality: { status: "GOOD", freshness: "UNAVAILABLE", source: "REPLAY" } }),
        ],
      }),
    );
    expect(cells.find((cell) => cell.id === "degraded")).toMatchObject({
      value: "0",
      tone: "neutral",
    });
  });

  it("prefers backend operator_surface_flag over local status inference", () => {
    const flagged = overviewDecisionKpis(
      input({
        opportunityItems: [
          row({
            data_quality: {
              status: "GOOD",
              freshness: "FRESH",
              operator_surface_flag: "STALE_OR_DEGRADED",
            },
          }),
        ],
      }),
    );
    expect(flagged.find((cell) => cell.id === "degraded")).toMatchObject({
      value: "1",
      tone: "caution",
    });

    const honestUnavailable = overviewDecisionKpis(
      input({
        opportunityItems: [
          row({
            data_quality: {
              status: "UNAVAILABLE",
              freshness: "UNAVAILABLE",
              operator_surface_flag: "OK",
            },
          }),
        ],
      }),
    );
    expect(honestUnavailable.find((cell) => cell.id === "degraded")).toMatchObject({
      value: "0",
      tone: "neutral",
    });
  });
});
