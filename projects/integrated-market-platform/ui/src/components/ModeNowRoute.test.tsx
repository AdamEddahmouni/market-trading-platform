import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("ModeNowRoute opportunity isolation", () => {
  it("does not import the opportunity client or review card from Live or the eager route", () => {
    const mode = readFileSync(new URL("./ModeNowRoute.tsx", import.meta.url), "utf8");
    const live = readFileSync(new URL("./live-now/LiveNowPage.tsx", import.meta.url), "utf8");
    const attention = readFileSync(new URL("./AttentionFeed.tsx", import.meta.url), "utf8");
    expect(mode).not.toContain("opportunityClient");
    expect(mode).not.toContain("useOpportunitiesSummaryQuery");
    expect(mode).not.toContain("OpportunityReviewCard");
    expect(live).not.toContain("opportunityClient");
    expect(live).not.toContain("OpportunityReviewCard");
    expect(attention).not.toContain("opportunityClient");
    expect(attention).not.toContain("OpportunityReviewCard");
  });
});
