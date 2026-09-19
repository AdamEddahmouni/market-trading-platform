import { describe, expect, it } from "vitest";
import {
  buildOpportunityEpistemicLayers,
  hasNonFactualResearchOutput,
} from "./opportunityEpistemicLayers";
import {
  fixtureOpportunityEvidenceRefresh,
  fixtureOpportunityRowBase,
} from "./opportunityDetailFixtures";

describe("opportunityEpistemicLayers", () => {
  it("marks agent enrichment as non-factual model output", () => {
    const layers = buildOpportunityEpistemicLayers(
      {
        ...fixtureOpportunityRowBase,
        metadata: { agent_enrichment: { status: "PARTIAL", count: 2 } },
      },
      fixtureOpportunityEvidenceRefresh,
    );
    expect(layers.model_research.some((row) => row.nonFactual && /agent/i.test(row.label))).toBe(true);
    expect(hasNonFactualResearchOutput(layers)).toBe(true);
  });

  it("surfaces grounded fact disposition when metadata carries extraction", () => {
    const layers = buildOpportunityEpistemicLayers({
      ...fixtureOpportunityRowBase,
      metadata: {
        grounded_fact_extraction: {
          disposition: "SUPPORTED_ANSWER",
          answer: "42",
          grounded_fact_extraction_version: "imp.grounded-fact-extraction/1.0.0",
        },
      },
    });
    expect(layers.observed.some((row) => row.label === "Grounded fact disposition")).toBe(true);
  });
});
