import { describe, expect, it } from "vitest";
import type { WorkspaceSqueezeResponse } from "../../api/schemas";
import { buildLaneModeContent } from "./buildLaneModeContent";

const squeezeFixture: WorkspaceSqueezeResponse = {
  symbol: "BIYA",
  source: "donor",
  bridge_mode: "READ_ONLY",
  available: true,
  replay_chart_available: false,
  ignition_state: "WATCH",
  freshness: "FROZEN",
  readiness: {
    freshness_state: "FROZEN",
    provenance_admissible: true,
  },
  phase3a_summary: "2 PASS / 1 UNKNOWN",
};

describe("buildLaneModeContent", () => {
  it("differentiates Demo, Paper, and Live squeeze headlines", () => {
    const base = {
      moduleId: "squeeze" as const,
      instrumentId: "BIYA",
      queryState: { phase: "ready" as const },
      data: squeezeFixture,
      dataMode: "frozen" as const,
    };

    const demo = buildLaneModeContent({ ...base, mode: "DEMO" });
    const paper = buildLaneModeContent({ ...base, mode: "PAPER" });
    const live = buildLaneModeContent({ ...base, mode: "LIVE" });

    expect(demo.headline).toMatch(/replay/i);
    expect(paper.headline).toMatch(/simulation readiness/i);
    expect(live.headline).toMatch(/observational/i);
    expect(paper.decisionHint).toBeDefined();
    expect(demo.decisionHint).toBeUndefined();
  });

  it("marks unavailable squeeze as degraded in Demo", () => {
    const content = buildLaneModeContent({
      mode: "DEMO",
      moduleId: "squeeze",
      instrumentId: "BIYA",
      queryState: { phase: "ready", degraded: true, message: "WHALE_NO_ENTITLED_SOURCE" },
      data: { ...squeezeFixture, available: false, reason: "WHALE_NO_ENTITLED_SOURCE" },
    });
    expect(content.summary).toContain("WHALE_NO_ENTITLED_SOURCE");
  });

  it("builds order-flow paper decision hint from bar delta", () => {
    const content = buildLaneModeContent({
      mode: "PAPER",
      moduleId: "order-flow",
      instrumentId: "NVDA",
      queryState: { phase: "ready" },
      data: {
        available: true,
        bars: [{ delta: 1200, cumulative_delta: 5000, aggressor_provenance: "UNKNOWN", quality: "OK", bar_time: "t", normalized_event_id: "1" }],
      },
    });
    expect(content.decisionHint).toBe("supports");
    expect(content.sections.some((section) => section.title === "Draft workflow")).toBe(true);
  });

  it("includes live canary link for Live order-book context", () => {
    const content = buildLaneModeContent({
      mode: "LIVE",
      moduleId: "order-book",
      instrumentId: "NVDA",
      queryState: { phase: "ready" },
      data: {
        available: true,
        symbol: "NVDA",
        latest_imbalance_ratio: 0.15,
        latest_book_state_valid: true,
      },
    });
    expect(content.relatedLinks?.some((link) => link.to === "/live-canary")).toBe(true);
  });
});
