import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function readSource(relativePath: string): string {
  return readFileSync(join(process.cwd(), "src/components", relativePath), "utf8");
}

describe("ModeNowRoute opportunity isolation", () => {
  it("does not import the opportunity client or queue from Live or the eager route", () => {
    const mode = readSource("ModeNowRoute.tsx");
    const live = readSource("live-now/LiveNowPage.tsx");
    const attention = readSource("AttentionFeed.tsx");
    expect(mode).not.toContain("opportunityClient");
    expect(mode).not.toContain("useOpportunitiesSummaryQuery");
    expect(mode).not.toContain("OpportunityQueue");
    expect(live).toContain("useOpportunitiesSummaryQuery");
    expect(live).not.toContain("OpportunityCard");
    expect(attention).not.toContain("opportunityClient");
    expect(attention).not.toContain("OpportunityQueue");
  });

  it("has no path back to the retired progressive opportunity card", () => {
    const queue = readSource("imp-product/ImpOverviewPrimaryQueue.tsx");
    const candidates = readSource("paper-now/PaperCandidateQueue.tsx");
    for (const source of [readSource("ModeNowRoute.tsx"), queue, candidates]) {
      expect(source).not.toContain("ProgressiveOpportunityCard");
      expect(source).not.toContain("OpportunityReviewCard");
      expect(source).not.toContain("progressiveOpportunityModel");
    }
  });
});
