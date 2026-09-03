import { describe, expect, it } from "vitest";
import { ExploreCatalystResponseSchema } from "./api/schemas";

describe("ExploreCatalystResponseSchema", () => {
  it("parses unavailable catalyst explore payload", () => {
    const parsed = ExploreCatalystResponseSchema.parse({
      available: false,
      source: "internship-project-main",
      bridge_mode: "READ_ONLY",
      reason: "Internship demo state not found.",
      rows: [],
      row_count: 0,
      decision_summary: [],
    });
    expect(parsed.available).toBe(false);
    expect(parsed.rows).toEqual([]);
  });

  it("parses available catalyst explore rows", () => {
    const parsed = ExploreCatalystResponseSchema.parse({
      available: true,
      source: "internship-project-main",
      bridge_mode: "READ_ONLY",
      row_count: 1,
      rows: [
        {
          catalyst_id: "catalyst:trade_log:BOXL:2026-01-01",
          symbol: "BOXL",
          headline: "BOXL catalyst signal",
          decision: "BUY",
          explanation_ref: "explain:catalyst:BOXL",
        },
      ],
      decision_summary: [{ label: "BUY", count: 1 }],
      disclaimer: "Donor catalyst rows are demo paper-research state.",
    });
    expect(parsed.rows?.[0]?.symbol).toBe("BOXL");
    expect(parsed.decision_summary?.[0]?.count).toBe(1);
  });
});
