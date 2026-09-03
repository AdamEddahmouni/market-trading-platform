import { describe, expect, it } from "vitest";
import { LANE_MODULE_IDS } from "../paper-now/paperOrderDraft";
import { buildPaperHandoffModel } from "./buildPaperHandoffModel";

describe("buildPaperHandoffModel", () => {
  it("returns manual state when no draft is provided", () => {
    const model = buildPaperHandoffModel(undefined, "BIYA");
    expect(model.kind).toBe("manual");
    expect(model.hasHandoff).toBe(false);
    expect(model.handoffSummary).toMatch(/No handoff/i);
  });

  it.each(LANE_MODULE_IDS)("supports known lane %s", (moduleId) => {
    const model = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: `lane:${moduleId}`,
      },
      "BIYA",
    );
    expect(model.kind).toBe("lane");
    expect(model.isLaneOriginated).toBe(true);
    expect(model.isUnknownLane).toBe(false);
    expect(model.sourceLane).toBe(moduleId);
    expect(model.handoffSummary).toMatch(/placeholder, not a recommendation/i);
  });

  it("flags unknown lane provenance safely", () => {
    const model = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: "lane:unknown",
      },
      "BIYA",
    );
    expect(model.isUnknownLane).toBe(true);
    expect(model.sourceLane).toBeNull();
    expect(model.warnings.length).toBeGreaterThan(0);
  });

  it("handles attention provenance with source context", () => {
    const model = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 2,
        orderType: "MARKET",
        sourceAttentionId: "attention-biya",
        sourceContext: {
          headline: "BIYA setup",
          tier: 1,
          reasons: [{ code: "PRICE_VOLUME", label: "Price and volume expanded" }],
        },
      },
      "BIYA",
    );
    expect(model.kind).toBe("attention");
    expect(model.isAttentionOriginated).toBe(true);
    expect(model.attentionId).toBe("attention-biya");
    expect(model.sourceContextSummary).toBe("BIYA setup");
    expect(model.sourceTier).toBe(1);
    expect(model.handoffSummary).toMatch(/Paper Command attention/i);
  });

  it("marks malformed drafts when symbol mismatches route", () => {
    const model = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "GME",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: "lane:squeeze",
      },
      "BIYA",
    );
    expect(model.isMalformed).toBe(true);
    expect(model.draftVersion).toBeNull();
  });

  it("degrades unsupported provenance prefixes", () => {
    const model = buildPaperHandoffModel(
      {
        version: 1,
        instrumentId: "BIYA",
        side: "BUY",
        quantity: 1,
        orderType: "MARKET",
        sourceAttentionId: "future:opaque",
      },
      "BIYA",
    );
    expect(model.kind).toBe("unknown");
    expect(model.warnings.some((warning) => warning.includes("future"))).toBe(true);
  });
});
