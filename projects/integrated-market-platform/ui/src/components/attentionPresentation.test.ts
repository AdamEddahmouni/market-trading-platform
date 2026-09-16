import { describe, expect, it } from "vitest";
import type { AttentionItem } from "../api/client";
import { attentionTierState, attentionWhyNow } from "./attentionPresentation";

function item(overrides: Partial<AttentionItem> = {}): AttentionItem {
  return {
    attention_id: "att-1",
    priority_rank: 1,
    headline: "Volume expands into the replay event",
    explanation_ref: "explain:attention:1",
    reasons: [{ code: "VOLUME_EXPANSION", label: "Volume exceeds the admitted baseline" }],
    ...overrides,
  };
}

describe("attentionTierState", () => {
  it("maps tiers to operator urgency language with text and tone", () => {
    expect(attentionTierState(1)).toEqual({
      tone: "caution",
      label: "Tier 1 — act now",
      raw: "TIER_1",
    });
    expect(attentionTierState(2).label).toBe("Tier 2 — review");
    expect(attentionTierState(2).tone).toBe("neutral");
    expect(attentionTierState(3).label).toBe("Tier 3 — monitor");
  });

  it("defaults a missing tier to review and preserves unknown tiers raw", () => {
    expect(attentionTierState(undefined).label).toBe("Tier 2 — review");
    expect(attentionTierState(7)).toEqual({ tone: "neutral", label: "Tier 7", raw: "TIER_7" });
  });
});

describe("attentionWhyNow", () => {
  it("joins distinct human reason labels in backend order", () => {
    const value = item({
      reasons: [
        { code: "REPLAY_ACTIVE", label: "Global REPLAY mode" },
        { code: "BAR_OHLCV", label: "Admitted equity intraday bars" },
      ],
    });
    expect(attentionWhyNow(value)).toBe("Global REPLAY mode; Admitted equity intraday bars");
  });

  it("deduplicates repeated labels and drops blank ones", () => {
    const value = item({
      reasons: [
        { code: "A", label: "Same reason" },
        { code: "B", label: "Same reason" },
        { code: "C", label: "   " },
      ],
    });
    expect(attentionWhyNow(value)).toBe("Same reason");
  });

  it("returns null when the contract carries no reasons", () => {
    expect(attentionWhyNow(item({ reasons: [] }))).toBeNull();
  });
});
