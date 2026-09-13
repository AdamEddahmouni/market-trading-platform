import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function readSource(relativePath: string): string {
  return readFileSync(join(process.cwd(), "src/components", relativePath), "utf8");
}

describe("ModeNowRoute opportunity isolation", () => {
  it("does not import the opportunity client or review card from Live or the eager route", () => {
    const mode = readSource("ModeNowRoute.tsx");
    const live = readSource("live-now/LiveNowPage.tsx");
    const attention = readSource("AttentionFeed.tsx");
    expect(mode).not.toContain("opportunityClient");
    expect(mode).not.toContain("useOpportunitiesSummaryQuery");
    expect(mode).not.toContain("OpportunityReviewCard");
    expect(live).not.toContain("opportunityClient");
    expect(live).not.toContain("OpportunityReviewCard");
    expect(attention).not.toContain("opportunityClient");
    expect(attention).not.toContain("OpportunityReviewCard");
  });
});
